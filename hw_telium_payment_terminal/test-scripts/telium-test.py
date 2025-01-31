#! /usr/bin/python3

from serial import Serial
import curses.ascii
import time
import pycountry
import logging
logger = logging.getLogger(__name__)

DEVICE = '/dev/ttyACM0'
DEVICE_RATE = 9600
PAYMENT_MODE = 'card'  # 'card' or 'check'
CURRENCY_ISO = 'EUR'
AMOUNT = 12.42


def serial_write(serial, text):
    assert isinstance(text, str), 'text must be a string'
    serial.write(text.encode('ascii'))


def initialize_msg(serial):
    max_attempt = 3
    attempt_nr = 0
    while attempt_nr < max_attempt:
        attempt_nr += 1
        send_one_byte_signal(serial, 'ENQ')
        if get_one_byte_answer(serial, 'ACK'):
            return True
        else:
            logger.info("Terminal : SAME PLAYER TRY AGAIN")
            send_one_byte_signal(serial, 'EOT')
            # Wait 1 sec between each attempt
            time.sleep(1)
    return False


def send_one_byte_signal(serial, signal):
    ascii_names = curses.ascii.controlnames
    assert signal in ascii_names, 'Wrong signal'
    char = ascii_names.index(signal)
    serial_write(serial, chr(char))
    logger.info('Signal %s sent to terminal' % signal)


def get_one_byte_answer(serial, expected_signal):
    ascii_names = curses.ascii.controlnames
    one_byte_read = serial.read(1).decode('ascii')
    expected_char = ascii_names.index(expected_signal)
    if one_byte_read == chr(expected_char):
        logger.info("%s received from terminal" % expected_signal)
        return True
    else:
        return False


def prepare_data_to_send():
    if PAYMENT_MODE == 'check':
        payment_mode = 'C'
    elif PAYMENT_MODE == 'card':
        payment_mode = '1'
    else:
        logger.info("The payment mode '%s' is not supported" % PAYMENT_MODE)
        return False
    cur_iso_letter = CURRENCY_ISO.upper()
    try:
        cur = pycountry.currencies.get(alpha_3=cur_iso_letter)
        cur_numeric = str(cur.numeric)
    except:
        logger.info("Currency %s is not recognized" % cur_iso_letter)
        return False
    data = {
        'pos_number': str(1).zfill(2),
        'answer_flag': '0',
        'transaction_type': '0',
        'payment_mode': payment_mode,
        'currency_numeric': cur_numeric.zfill(3),
        'private': ' ' * 10,
        'delay': 'A011',
        'auto': 'B010',
        'amount_msg': ('%.0f' % (AMOUNT * 100)).zfill(8),
    }
    return data


def generate_lrc(real_msg_with_etx):
    lrc = 0
    for char in real_msg_with_etx:
        lrc ^= ord(char)
    return lrc


def send_message(serial, data):
    '''We use protocol E+'''
    ascii_names = curses.ascii.controlnames
    real_msg = (
        data['pos_number'] +
        data['amount_msg'] +
        data['answer_flag'] +
        data['payment_mode'] +
        data['transaction_type'] +
        data['currency_numeric'] +
        data['private'] +
        data['delay'] +
        data['auto'])
    logger.info('Real message to send = %s' % real_msg)
    assert len(real_msg) == 34, 'Wrong length for protocol E+'
    real_msg_with_etx = real_msg + chr(ascii_names.index('ETX'))
    lrc = generate_lrc(real_msg_with_etx)
    message = chr(ascii_names.index('STX')) + real_msg_with_etx + chr(lrc)
    serial_write(serial, message)
    logger.info('Message sent to terminal')


def compare_data_vs_answer(data, answer_data):
    for field in [
            'pos_number', 'amount_msg',
            'currency_numeric', 'private']:
        if data[field] != answer_data[field]:
            logger.info(
                "Field %s has value '%s' in data and value '%s' in answer"
                % (field, data[field], answer_data[field]))


def parse_terminal_answer(real_msg, data):
    answer_data = {
        'pos_number': real_msg[0:2],
        'transaction_result': real_msg[2],
        'amount_msg': real_msg[3:11],
        'payment_mode': real_msg[11],
        'currency_numeric': real_msg[12:15],
        'private': real_msg[15:26],
    }
    logger.info('answer_data = %s' % answer_data)
    compare_data_vs_answer(data, answer_data)
    return answer_data


def get_answer_from_terminal(serial, data):
    ascii_names = curses.ascii.controlnames
    full_msg_size = 1+2+1+8+1+3+10+1+1
    msg = serial.read(size=full_msg_size).decode('ascii')
    logger.info('%d bytes read from terminal' % full_msg_size)
    assert len(msg) == full_msg_size, 'Answer has a wrong size'
    if msg[0] != chr(ascii_names.index('STX')):
        logger.info('The first byte of the answer from terminal should be STX')
    if msg[-2] != chr(ascii_names.index('ETX')):
        logger.info('The byte before final of the answer '
              'from terminal should be ETX')
    lrc = msg[-1]
    computed_lrc = chr(generate_lrc(msg[1:-1]))
    if computed_lrc != lrc:
        logger.info('The LRC of the answer from terminal is wrong')
    real_msg = msg[1:-2]
    logger.info('Real answer received = %s' % real_msg)
    return parse_terminal_answer(real_msg, data)


def transaction_start():
    '''This function sends the data to the serial/usb port.
    '''
    serial = False
    try:
        logger.info(
            'Opening serial port %s for payment terminal with '
            'baudrate %d' % (DEVICE, DEVICE_RATE))
        # IMPORTANT : don't modify timeout=3 seconds
        # This parameter is very important ; the Telium spec say
        # that we have to wait to up 3 seconds to get LRC
        serial = Serial(
            DEVICE, DEVICE_RATE, timeout=3)
        logger.info('serial.is_open = %s' % serial.isOpen())
        if initialize_msg(serial):
            data = prepare_data_to_send()
            if not data:
                return
            send_message(serial, data)
            if get_one_byte_answer(serial, 'ACK'):
                send_one_byte_signal(serial, 'EOT')

                logger.info("Now expecting answer from Terminal")
                if get_one_byte_answer(serial, 'ENQ'):
                    send_one_byte_signal(serial, 'ACK')
                    get_answer_from_terminal(serial, data)
                    send_one_byte_signal(serial, 'ACK')
                    if get_one_byte_answer(serial, 'EOT'):
                        logger.info("Answer received from Terminal")

    except Exception as e:
        logger.info('Exception in serial connection: %s' % str(e))
    finally:
        if serial:
            logger.info('Closing serial port for payment terminal')
            serial.close()


if __name__ == '__main__':
    transaction_start()

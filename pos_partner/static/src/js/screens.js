odoo.define("pos_partner.screens", function(require) {
    "use strict";

    var screens = require("point_of_sale.screens");
    var gui = require('point_of_sale.gui');
    var core = require('web.core');
    var _t = core._t;

    screens.PaymentScreenWidget.include({
        validate_order: function(force_validation) {
            var order = this.pos.get_order();
            var client = order.get_client();

            // Use the variable name you chose: 'pos_require_customer_id'
            if (this.pos.config.pos_require_customer_id && client && !client.vat) {
                this.gui.show_popup('error', {
                    'title': _t('Identificación del cliente requerida'),
                    'body': _t("Debes registrar la identificación del cliente antes de continuar con la venta."),
                });
                return;
            }
            this._super(force_validation);
        }
    });

    screens.ClientListScreenWidget.include({
        save_client_details: function(partner) {
            var vat_value = this.$('.client-details-contents input[name="vat"]').val();
            if (this.pos.config.pos_require_customer_id && !vat_value) {
                this.gui.show_popup('error', {
                    'title': _t('Identificación del cliente requerida'),
                    'body': _t("Debes ingresar el número de identificación del cliente para poder guardar."),
                });
                return;
            }            
            this._super(partner);
        },
        
        line_select: function(event, $line, id) {
            try {
                var partner = this.pos.db.get_partner_by_id(id);
                const datebirt = new Date(partner.fecha_nac);
                const datenow = new Date();
                // Check for birthday
                if (
                    datebirt.getUTCDate() === datenow.getUTCDate() &&
                    datebirt.getUTCMonth() === datenow.getUTCMonth()
                ) {
                    this.confetti_start();
                }
            } catch (err) {
                console.log(err);
            }
            return this._super(event, $line, id);
        },

        confetti_start: function() {
            var self = this;
            if (!this.confetti) {
                this.confetti_init();
            }
            this.confetti.start();
            setTimeout(function() {
                self.confetti.stop();
            }, 5000);
        },

        confetti_init: function() {
            var self = this;
            self.confetti = {
                maxCount: 100,
                speed: 1,
                frameInterval: 15,
                alpha: 1.0,
                gradient: false,
                start: null,
                stop: null,
                toggle: null,
                pause: null,
                resume: null,
                togglePause: null,
                remove: null,
                isPaused: null,
                isRunning: null,
            };

            var supportsAnimationFrame =
                window.requestAnimationFrame ||
                window.webkitRequestAnimationFrame ||
                window.mozRequestAnimationFrame ||
                window.oRequestAnimationFrame ||
                window.msRequestAnimationFrame;
            var colors = [
                "rgba(30,144,255,",
                "rgba(107,142,35,",
                "rgba(255,215,0,",
                "rgba(255,192,203,",
                "rgba(106,90,205,",
                "rgba(173,216,230,",
                "rgba(238,130,238,",
                "rgba(152,251,152,",
                "rgba(70,130,180,",
                "rgba(244,164,96,",
                "rgba(210,105,30,",
                "rgba(220,20,60,",
            ];
            var streamingConfetti = false;
            var pause = false;
            var lastFrameTime = Date.now();
            var particles = [];
            var waveAngle = 0;
            var context = null;

            function resetParticle(particle, width, height) {
                particle.color =
                    colors[(Math.random() * colors.length) | 0] +
                    (self.confetti.alpha + ")");
                particle.color2 =
                    colors[(Math.random() * colors.length) | 0] +
                    (self.confetti.alpha + ")");
                particle.x = Math.random() * width;
                particle.y = Math.random() * height - height;
                particle.diameter = Math.random() * 10 + 5;
                particle.tilt = Math.random() * 10 - 10;
                particle.tiltAngleIncrement = Math.random() * 0.07 + 0.05;
                particle.tiltAngle = Math.random() * Math.PI;
                return particle;
            }

            function drawParticles(context) {
                var particle = [];
                let x = 0,
                    x2 = 0,
                    y2 = 0;
                for (var i = 0; i < particles.length; i++) {
                    particle = particles[i];
                    context.beginPath();
                    context.lineWidth = particle.diameter;
                    x2 = particle.x + particle.tilt;
                    x = x2 + particle.diameter / 2;
                    y2 = particle.y + particle.tilt + particle.diameter / 2;
                    if (self.confetti.gradient) {
                        var gradient = context.createLinearGradient(
                            x,
                            particle.y,
                            x2,
                            y2
                        );
                        gradient.addColorStop("0", particle.color);
                        gradient.addColorStop("1.0", particle.color2);
                        context.strokeStyle = gradient;
                    } else context.strokeStyle = particle.color;
                    context.moveTo(x, particle.y);
                    context.lineTo(x2, y2);
                    context.stroke();
                }
            }

            function updateParticles() {
                var width = window.innerWidth;
                var height = window.innerHeight;
                var particle = [];
                waveAngle += 0.01;
                for (var i = 0; i < particles.length; i++) {
                    particle = particles[i];
                    if (!streamingConfetti && particle.y < -15)
                        particle.y = height + 100;
                    else {
                        particle.tiltAngle += particle.tiltAngleIncrement;
                        particle.x += Math.sin(waveAngle) - 0.5;
                        particle.y +=
                            (Math.cos(waveAngle) +
                                particle.diameter +
                                self.confetti.speed) *
                            0.5;
                        particle.tilt = Math.sin(particle.tiltAngle) * 15;
                    }
                    if (
                        particle.x > width + 20 ||
                        particle.x < -20 ||
                        particle.y > height
                    ) {
                        if (
                            streamingConfetti &&
                            particles.length <= self.confetti.maxCount
                        )
                            resetParticle(particle, width, height);
                        else {
                            particles.splice(i, 1);
                            i--;
                        }
                    }
                }
            }

            function runAnimation() {
                if (pause) return;
                else if (particles.length === 0) {
                    context.clearRect(0, 0, window.innerWidth, window.innerHeight);
                } else {
                    var now = Date.now();
                    var delta = now - lastFrameTime;
                    if (
                        !supportsAnimationFrame ||
                        delta > self.confetti.frameInterval
                    ) {
                        context.clearRect(0, 0, window.innerWidth, window.innerHeight);
                        updateParticles();
                        drawParticles(context);
                        lastFrameTime = now - (delta % self.confetti.frameInterval);
                    }
                    requestAnimationFrame(runAnimation);
                }

            }

            function resumeConfetti() {
                pause = false;
                runAnimation();
            }

            function pauseConfetti() {
                pause = true;
            }

            function toggleConfettiPause() {
                if (pause) resumeConfetti();
                else pauseConfetti();
            }

            function isConfettiPaused() {
                return pause;
            }

            function stopConfetti() {
                streamingConfetti = false;
            }

            function startConfetti(timeout, min, max) {
                var width = window.innerWidth;
                var height = window.innerHeight;
                window.requestAnimationFrame = (function() {
                    return (
                        window.requestAnimationFrame ||
                        window.webkitRequestAnimationFrame ||
                        window.mozRequestAnimationFrame ||
                        window.oRequestAnimationFrame ||
                        window.msRequestAnimationFrame ||
                        function(callback) {
                            return window.setTimeout(
                                callback,
                                self.confetti.frameInterval
                            );
                        }
                    );
                })();
                var canvas = document.getElementById("confetti-canvas");
                if (canvas === null) {
                    canvas = document.createElement("canvas");
                    canvas.setAttribute("id", "confetti-canvas");
                    canvas.setAttribute(
                        "style",
                        "display:block;z-index:999999;pointer-events:none;position:fixed;top:0"
                    );
                    document.body.prepend(canvas);
                    canvas.width = width;
                    canvas.height = height;
                    window.addEventListener(
                        "resize",
                        function() {
                            canvas.width = window.innerWidth;
                            canvas.height = window.innerHeight;
                        },
                        true
                    );
                    context = canvas.getContext("2d");
                } else if (context === null) context = canvas.getContext("2d");
                var count = self.confetti.maxCount;
                if (min) {
                    if (max) {
                        if (min == max) count = particles.length + max;
                        else {
                            if (min > max) {
                                var temp = min;
                                min = max;
                                max = temp;
                            }
                            count =
                                particles.length +
                                ((Math.random() * (max - min) + min) | 0);
                        }
                    } else count = particles.length + min;
                } else if (max) count = particles.length + max;
                while (particles.length < count)
                    particles.push(resetParticle({}, width, height));
                streamingConfetti = true;
                pause = false;
                runAnimation();
                if (timeout) {
                    window.setTimeout(stopConfetti, timeout);
                }
            }

            function removeConfetti() {
                stop();
                pause = false;
                particles = [];
            }

            function toggleConfetti() {
                if (streamingConfetti) stopConfetti();
                else startConfetti();
            }

            function isConfettiRunning() {
                return streamingConfetti;
            }

            self.confetti.start = startConfetti;
            self.confetti.stop = stopConfetti;
            self.confetti.toggle = toggleConfetti;
            self.confetti.pause = pauseConfetti;
            self.confetti.resume = resumeConfetti;
            self.confetti.togglePause = toggleConfettiPause;
            self.confetti.isPaused = isConfettiPaused;
            self.confetti.remove = removeConfetti;
            self.confetti.isRunning = isConfettiRunning;
        },
    });
});

// Sokaktan Dijitale - Tailwind Tema Yapilandirmasi
tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            cream: '#FAF6F0',
                            sand: '#EFEAE2',
                            rust: '#D9383A',
                            charcoal: '#1C1C1C',
                            muted: '#5C554E',
                            darkrust: '#B92A2C',
                            lightrust: '#FDECEB'
                        }
                    },
                    fontFamily: {
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        serif: ['"Playfair Display"', 'serif'],
                    },
                    animation: {
                        'marquee': 'marquee 30s linear infinite',
                        'marquee2': 'marquee2 30s linear infinite',
                        'float': 'float 6s ease-in-out infinite',
                        'float-delayed': 'float 6s ease-in-out infinite 3s',
                        'fade-in-up': 'fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
                        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                    },
                    keyframes: {
                        marquee: {
                            '0%': { transform: 'translateX(0%)' },
                            '100%': { transform: 'translateX(-100%)' }
                        },
                        marquee2: {
                            '0%': { transform: 'translateX(100%)' },
                            '100%': { transform: 'translateX(0%)' }
                        },
                        float: {
                            '0%, 100%': { transform: 'translateY(0px)' },
                            '50%': { transform: 'translateY(-15px)' }
                        },
                        fadeInUp: {
                            '0%': { opacity: '0', transform: 'translateY(30px)' },
                            '100%': { opacity: '1', transform: 'translateY(0)' }
                        }
                    }
                }
            }
        };

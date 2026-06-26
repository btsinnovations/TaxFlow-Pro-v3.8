import { useEffect, useRef } from 'react';
import { ArrowDown, Shield, FileText, Zap } from 'lucide-react';

const Hero = () => {
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (heroRef.current) {
        heroRef.current.classList.add('opacity-100');
      }
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <section
      ref={heroRef}
      id="hero"
      className="relative min-h-screen flex items-center justify-center bg-black overflow-hidden opacity-0 transition-opacity duration-1000"
    >
      {/* Subtle noise texture */}
      <div 
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />
      
      {/* Bottom accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#C9A96E]/30 to-transparent" />

      <div className="relative z-10 text-center px-6 max-w-4xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#C9A96E]/30 bg-[#C9A96E]/5 mb-8">
          <Shield className="w-4 h-4 text-[#C9A96E]" />
          <span className="text-sm text-[#C9A96E] font-medium tracking-wide uppercase">
            Financial ETL Pipeline v3.5.4
          </span>
        </div>

        <h1 className="font-serif text-5xl md:text-7xl lg:text-8xl text-white mb-6 tracking-tight leading-[1.1]">
          TaxFlow
          <span className="block text-[#C9A96E]">Pro</span>
        </h1>

        <p className="text-lg md:text-xl text-white/60 max-w-2xl mx-auto mb-12 leading-relaxed">
          Enterprise-grade bank statement processing with client isolation, 
          audit trails, and intelligent categorization. 
          <span className="text-white/90"> PDF & CSV supported.</span>
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <a
            href="#upload"
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#C9A96E] text-black font-medium rounded-lg hover:bg-[#B8975E] transition-colors"
          >
            <FileText className="w-5 h-5" />
            Upload Statements
          </a>
          <a
            href="#dashboard"
            className="inline-flex items-center gap-2 px-8 py-4 border border-white/20 text-white font-medium rounded-lg hover:bg-white/5 transition-colors"
          >
            <Zap className="w-5 h-5" />
            View Dashboard
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left max-w-3xl mx-auto">
          <div className="p-4 rounded-lg border border-white/10 bg-white/[0.02]">
            <div className="text-[#C9A96E] text-2xl font-serif mb-1">16+</div>
            <div className="text-white/50 text-sm">Supported Institutions</div>
          </div>
          <div className="p-4 rounded-lg border border-white/10 bg-white/[0.02]">
            <div className="text-[#C9A96E] text-2xl font-serif mb-1">100%</div>
            <div className="text-white/50 text-sm">Offline Processing</div>
          </div>
          <div className="p-4 rounded-lg border border-white/10 bg-white/[0.02]">
            <div className="text-[#C9A96E] text-2xl font-serif mb-1">PDF/CSV/OFX</div>
            <div className="text-white/50 text-sm">Input Formats</div>
          </div>
        </div>
      </div>

      <a
        href="#upload"
        className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white/30 hover:text-[#C9A96E] transition-colors animate-bounce"
      >
        <ArrowDown className="w-6 h-6" />
      </a>
    </section>
  );
};

export default Hero;

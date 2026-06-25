import { useEffect, useState } from 'react';

export default function Footer() {
  const [version, setVersion] = useState('');
  const links = ['Documentation', 'Support', 'Privacy', 'Terms'];

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setVersion(data.version || ''))
      .catch(() => setVersion(''));
  }, []);

  return (
    <footer className="bg-canvas border-t border-divider px-4 md:px-8 py-8 mt-12">
      <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="font-serif text-base text-gold">TaxFlow Pro</div>
        <div className="font-mono text-xs text-text-secondary">{version ? `v${version}` : ''}</div>
        <div className="flex items-center gap-6">
          {links.map(link => (
            <a
              key={link}
              href="#"
              className="font-sans text-[13px] text-text-secondary transition-colors duration-200 hover:text-text-primary"
            >
              {link}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}

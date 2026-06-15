import { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { taxRules } from '@/data/mockData';
import type { TaxRule } from '@/data/mockData';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const entityTypeConfig: Record<string, { bg: string; text: string }> = {
  Individual: { bg: 'rgba(96, 165, 250, 0.15)', text: '#60A5FA' },
  'S-Corp': { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  Partnership: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
  LLC: { bg: 'rgba(201, 169, 110, 0.15)', text: '#C9A96E' },
  'C-Corp': { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
};

const categoryTabs = ['All', 'Deductions', 'Income', 'Credits', 'Depreciation'];

function ToggleSwitch({ enabled }: { enabled: boolean }) {
  return (
    <div
      className="w-9 h-5 rounded-full relative transition-colors duration-200"
      style={{ backgroundColor: enabled ? '#4ADE80' : '#3A3A3A' }}
    >
      <div
        className="w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 transition-all duration-200"
        style={{ left: enabled ? '18px' : '2px' }}
      />
    </div>
  );
}

export default function TaxRules() {
  const [selectedRule, setSelectedRule] = useState<TaxRule>(taxRules[0]);
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      if (leftRef.current) {
        gsap.fromTo(leftRef.current, { opacity: 0, x: -20 }, {
          opacity: 1, x: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: leftRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        });
      }
      if (rightRef.current) {
        gsap.fromTo(rightRef.current, { opacity: 0, x: 20 }, {
          opacity: 1, x: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: rightRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        });
      }
    });
    return () => ctx.revert();
  }, []);

  const filteredRules = taxRules.filter(rule => {
    const matchesCategory = activeCategory === 'All' || rule.category === activeCategory;
    const matchesSearch = !searchQuery || rule.name.toLowerCase().includes(searchQuery.toLowerCase()) || rule.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <section id="tax-rules" className="bg-canvas px-4 md:px-8 py-8">
      <div className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Tax Rules Engine</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Configure deduction rules, category mappings, and entity-specific tax treatments.
          </p>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left Panel - Rules List */}
          <div ref={leftRef} className="lg:col-span-3 space-y-4">
            {/* Search */}
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
              <input
                type="text"
                placeholder="Search rules..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-surface border border-divider rounded-md pl-10 pr-4 py-2.5 font-sans text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none transition-colors"
              />
            </div>

            {/* Category Tabs */}
            <div className="flex flex-wrap gap-2">
              {categoryTabs.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveCategory(tab)}
                  className="font-mono text-[11px] uppercase tracking-wide px-3 py-1.5 rounded transition-all duration-200"
                  style={{
                    backgroundColor: activeCategory === tab ? 'rgba(201, 169, 110, 0.15)' : 'transparent',
                    color: activeCategory === tab ? '#C9A96E' : '#8A8A8A',
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Rules List */}
            <div className="space-y-2">
              {filteredRules.map(rule => (
                <button
                  key={rule.id}
                  onClick={() => setSelectedRule(rule)}
                  className="w-full text-left bg-surface border rounded-md p-4 transition-all duration-200 hover:border-divider-active"
                  style={{
                    borderColor: selectedRule.id === rule.id ? '#C9A96E' : '#2A2A2A',
                    borderLeftWidth: selectedRule.id === rule.id ? '3px' : '1px',
                    borderLeftColor: selectedRule.id === rule.id ? '#C9A96E' : '#2A2A2A',
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-sans text-sm font-medium text-text-primary">{rule.name}</span>
                    <div className="flex gap-1">
                      {rule.appliesTo.map(entity => (
                        <span
                          key={entity}
                          className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                          style={{ backgroundColor: entityTypeConfig[entity]?.bg, color: entityTypeConfig[entity]?.text }}
                        >
                          {entity}
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="font-sans text-xs text-text-secondary">{rule.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Right Panel - Rule Detail */}
          <div ref={rightRef} className="lg:col-span-2">
            <div className="bg-surface border border-divider rounded-lg p-6 sticky top-20">
              <h3 className="font-serif text-xl text-text-primary mb-4">{selectedRule.name}</h3>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Rule ID</div>
                  <div className="font-mono text-sm text-text-primary">{selectedRule.id}</div>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Category</div>
                  <div className="font-sans text-sm text-text-primary">{selectedRule.category}</div>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Applies To</div>
                  <div className="flex flex-wrap gap-1">
                    {selectedRule.appliesTo.map(entity => (
                      <span
                        key={entity}
                        className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: entityTypeConfig[entity]?.bg, color: entityTypeConfig[entity]?.text }}
                      >
                        {entity}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Effective Date</div>
                  <div className="font-mono text-sm text-text-primary">{selectedRule.effectiveDate}</div>
                </div>
                {selectedRule.threshold && (
                  <div>
                    <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Threshold</div>
                    <div className="font-sans text-sm text-text-primary">{selectedRule.threshold}</div>
                  </div>
                )}
                {selectedRule.maximum && (
                  <div>
                    <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Maximum</div>
                    <div className="font-sans text-sm text-text-primary">{selectedRule.maximum}</div>
                  </div>
                )}
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Override Allowed</div>
                  <ToggleSwitch enabled={selectedRule.overrideAllowed} />
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Auto-Apply</div>
                  <ToggleSwitch enabled={selectedRule.autoApply} />
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button className="flex-1 bg-gold text-canvas font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover">
                  Edit Rule
                </button>
                <button className="flex-1 border border-gold text-gold bg-transparent font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-muted">
                  Test Rule
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

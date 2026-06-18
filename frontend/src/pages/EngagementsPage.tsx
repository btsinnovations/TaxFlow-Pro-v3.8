import { useEffect, useState, useRef, useCallback } from 'react';
import { ClipboardList, Eye, Plus, AlertCircle, CheckCircle, FileText } from 'lucide-react';
import {
  getEngagementTemplates, getEngagementTemplate, createEngagementFromTemplate,
} from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface TemplateSummary {
  template_type: string;
  name: string;
  description: string;
}

interface TemplateDetail extends TemplateSummary {
  body: string;
  default_fee: number | null;
  checklist_items: string[];
}

export default function EngagementsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Template detail
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDetail | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);

  // Create engagement
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    engagement_name: '',
    due_date: '',
    custom_fee: '',
    notes: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEngagementTemplates();
      setTemplates(data);
    } catch {
      setError('Failed to load engagement templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        sectionRef.current,
        { opacity: 0, y: 30 },
        {
          opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        }
      );
    }, sectionRef);
    return () => ctx.revert();
  }, [loading, templates]);

  const loadTemplate = async (templateType: string) => {
    setTemplateLoading(true);
    try {
      const data = await getEngagementTemplate(templateType);
      setSelectedTemplate(data);
    } catch (e: any) {
      toast({ title: 'Failed', description: e.message, variant: 'destructive' });
    } finally {
      setTemplateLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!selectedClient || !selectedTemplate) return;
    try {
      const result = await createEngagementFromTemplate({
        template_type: selectedTemplate.template_type,
        client_id: selectedClient.id,
        engagement_name: createForm.engagement_name || undefined,
        due_date: createForm.due_date || undefined,
        custom_fee: createForm.custom_fee ? parseFloat(createForm.custom_fee) : undefined,
        notes: createForm.notes || undefined,
      });
      toast({ title: 'Engagement created', description: result.name });
      setCreateOpen(false);
      setSelectedTemplate(null);
      setCreateForm({ engagement_name: '', due_date: '', custom_fee: '', notes: '' });
    } catch (e: any) {
      toast({ title: 'Create failed', description: e.message, variant: 'destructive' });
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <ClipboardList className="text-gold" size={28} />
            Engagements
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Browse engagement templates and create client engagements.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        {loading ? (
          <div className="text-text-secondary text-sm">Loading templates...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map(t => (
              <Card key={t.template_type} className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-sm font-medium text-text-primary">{t.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="font-sans text-xs text-text-secondary mb-4">{t.description}</p>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1 text-xs" onClick={() => loadTemplate(t.template_type)}>
                      <Eye size={12} className="mr-1" /> Preview
                    </Button>
                    <Button size="sm" variant="outline" className="text-xs bg-gold/10 border-gold/30 text-gold hover:bg-gold/20" onClick={() => { loadTemplate(t.template_type); setTimeout(() => setCreateOpen(true), 500); }}>
                      <Plus size={12} className="mr-1" /> Create
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Template Detail Dialog */}
        <Dialog open={!!selectedTemplate} onOpenChange={(open) => { if (!open) setSelectedTemplate(null); }}>
          <DialogContent className="bg-surface border-divider text-text-primary max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-sans text-sm">{selectedTemplate?.name}</DialogTitle>
            </DialogHeader>
            {templateLoading ? (
              <div className="py-8 text-center text-text-secondary">Loading template...</div>
            ) : selectedTemplate ? (
              <div className="space-y-4 py-2">
                <p className="font-sans text-sm text-text-secondary">{selectedTemplate.description}</p>

                {selectedTemplate.default_fee && (
                  <div className="bg-canvas rounded-lg p-3">
                    <span className="font-sans text-xs text-text-secondary">Default Fee: </span>
                    <span className="font-mono text-sm text-gold">${selectedTemplate.default_fee.toFixed(2)}</span>
                  </div>
                )}

                {selectedTemplate.checklist_items.length > 0 && (
                  <div>
                    <h4 className="font-sans text-xs font-medium text-text-primary mb-2 flex items-center gap-1">
                      <CheckCircle size={12} className="text-emerald-400" />
                      Checklist ({selectedTemplate.checklist_items.length} items)
                    </h4>
                    <ul className="space-y-1">
                      {selectedTemplate.checklist_items.map((item, i) => (
                        <li key={i} className="font-sans text-xs text-text-secondary flex items-center gap-2">
                          <span className="w-1 h-1 rounded-full bg-gold" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div>
                  <h4 className="font-sans text-xs font-medium text-text-primary mb-2 flex items-center gap-1">
                    <FileText size={12} className="text-gold" />
                    Engagement Letter Preview
                  </h4>
                  <pre className="bg-canvas rounded-lg p-4 text-xs text-text-primary whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
                    {selectedTemplate.body}
                  </pre>
                </div>
              </div>
            ) : null}
            <DialogFooter>
              <Button variant="ghost" onClick={() => setSelectedTemplate(null)}>Close</Button>
              {selectedTemplate && (
                <Button className="bg-gold text-black hover:bg-gold/90" onClick={() => { setCreateOpen(true); }}>
                  <Plus size={14} className="mr-1" /> Create Engagement
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Create Engagement Dialog */}
        <Dialog open={createOpen} onOpenChange={(open) => { if (!open) { setCreateOpen(false); setSelectedTemplate(null); } }}>
          <DialogContent className="bg-surface border-divider text-text-primary">
            <DialogHeader>
              <DialogTitle className="font-sans text-sm">Create Engagement</DialogTitle>
            </DialogHeader>
            {selectedTemplate && (
              <div className="space-y-3 py-2">
                <div className="bg-canvas rounded-lg p-3">
                  <span className="font-sans text-xs text-text-secondary">Template: </span>
                  <span className="font-sans text-sm text-text-primary">{selectedTemplate.name}</span>
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Engagement Name (optional)</Label>
                  <Input
                    value={createForm.engagement_name}
                    onChange={e => setCreateForm(f => ({ ...f, engagement_name: e.target.value }))}
                    placeholder={`Defaults to: ${selectedTemplate.name}`}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Due Date (optional)</Label>
                  <Input type="date" value={createForm.due_date} onChange={e => setCreateForm(f => ({ ...f, due_date: e.target.value }))} className="bg-canvas border-divider text-sm" />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Custom Fee (optional)</Label>
                  <Input type="number" step="0.01" value={createForm.custom_fee} onChange={e => setCreateForm(f => ({ ...f, custom_fee: e.target.value }))} placeholder={`Default: ${selectedTemplate.default_fee}`} className="bg-canvas border-divider text-sm" />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Notes (optional)</Label>
                  <Input
                    value={createForm.notes}
                    onChange={e => setCreateForm(f => ({ ...f, notes: e.target.value }))}
                    placeholder="Any additional notes"
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="ghost" onClick={() => { setCreateOpen(false); setSelectedTemplate(null); }}>Cancel</Button>
              <Button onClick={handleCreate} className="bg-gold text-black hover:bg-gold/90">Create Engagement</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </section>
  );
}

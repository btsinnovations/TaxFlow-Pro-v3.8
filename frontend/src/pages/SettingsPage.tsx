import { useEffect, useState, useRef, useCallback } from 'react';
import { Settings, Save, AlertCircle, Shield, Image } from 'lucide-react';
import {
  getSettings, updateSettings, uploadLogo, getThresholds, updateThresholds,
} from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface FirmSettings {
  firm_name: string | null;
  firm_address: string | null;
  firm_phone: string | null;
  firm_email: string | null;
  firm_ein: string | null;
  logo_path: string | null;
  fiscal_year_end: string | null;
  timezone: string | null;
  date_format: string | null;
}

interface Thresholds {
  high_confidence: number;
  medium_confidence: number;
  auto_confirm: number;
}

export default function SettingsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  // Firm settings
  const [settings, setSettings] = useState<Partial<FirmSettings>>({});
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);

  // Thresholds
  const [thresholds, setThresholds] = useState<Thresholds>({ high_confidence: 0.85, medium_confidence: 0.60, auto_confirm: 0.95 });
  const [thresholdsLoading, setThresholdsLoading] = useState(true);
  const [savingThresholds, setSavingThresholds] = useState(false);

  // Error
  const [error, setError] = useState('');

  const fetchSettings = useCallback(async () => {
    if (!selectedClient) return;
    setSettingsLoading(true);
    try {
      const data = await getSettings(selectedClient.id);
      setSettings(data);
    } catch {
      setError('Failed to load settings');
    } finally {
      setSettingsLoading(false);
    }
  }, [selectedClient]);

  const fetchThresholds = useCallback(async () => {
    if (!selectedClient) return;
    setThresholdsLoading(true);
    try {
      const data = await getThresholds(selectedClient.id);
      setThresholds(data);
    } catch {
      // Use defaults
    } finally {
      setThresholdsLoading(false);
    }
  }, [selectedClient]);

  useEffect(() => {
    fetchSettings();
    fetchThresholds();
  }, [fetchSettings, fetchThresholds]);

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
  }, []);

  const handleSaveSettings = async () => {
    if (!selectedClient) return;
    setSaving(true);
    try {
      const data = await updateSettings(selectedClient.id, {
        firm_name: settings.firm_name || undefined,
        firm_address: settings.firm_address || undefined,
        firm_phone: settings.firm_phone || undefined,
        firm_email: settings.firm_email || undefined,
        firm_ein: settings.firm_ein || undefined,
        fiscal_year_end: settings.fiscal_year_end || undefined,
        timezone: settings.timezone || undefined,
        date_format: settings.date_format || undefined,
      });
      setSettings(data);
      toast({ title: 'Settings saved', description: 'Firm settings updated successfully.' });
    } catch (e: any) {
      toast({ title: 'Save failed', description: e.message, variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedClient || !e.target.files?.[0]) return;
    setLogoUploading(true);
    try {
      const result = await uploadLogo(selectedClient.id, e.target.files[0]);
      toast({ title: 'Logo uploaded', description: result.filename });
      setSettings(s => ({ ...s, logo_path: result.logo_path }));
    } catch (err: any) {
      toast({ title: 'Upload failed', description: err.message, variant: 'destructive' });
    } finally {
      setLogoUploading(false);
    }
  };

  const handleSaveThresholds = async () => {
    if (!selectedClient) return;
    if (thresholds.high_confidence < thresholds.medium_confidence) {
      toast({ title: 'Invalid thresholds', description: 'High confidence must be >= Medium confidence.', variant: 'destructive' });
      return;
    }
    setSavingThresholds(true);
    try {
      const data = await updateThresholds(selectedClient.id, thresholds);
      setThresholds(data);
      toast({ title: 'Thresholds saved', description: 'Recurring transaction thresholds updated.' });
    } catch (e: any) {
      toast({ title: 'Save failed', description: e.message, variant: 'destructive' });
    } finally {
      setSavingThresholds(false);
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <Settings className="text-gold" size={28} />
            Firm Settings
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Manage firm details, logo, and recurring-transaction confidence thresholds.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        <Tabs defaultValue="firm" className="space-y-6">
          <TabsList className="bg-surface border-divider">
            <TabsTrigger value="firm" className="data-[state=active]:bg-gold/10 data-[state=active]:text-gold">Firm Details</TabsTrigger>
            <TabsTrigger value="logo" className="data-[state=active]:bg-gold/10 data-[state=active]:text-gold">Logo</TabsTrigger>
            <TabsTrigger value="thresholds" className="data-[state=active]:bg-gold/10 data-[state=active]:text-gold">ML Thresholds</TabsTrigger>
          </TabsList>

          {/* Firm Details Tab */}
          <TabsContent value="firm">
            <Card className="bg-surface border-divider">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="font-sans text-sm font-medium text-text-primary">Firm Information</CardTitle>
                <Button size="sm" className="bg-gold text-black hover:bg-gold/90" onClick={handleSaveSettings} disabled={saving}>
                  <Save size={14} className="mr-1" /> {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </CardHeader>
              <CardContent>
                {settingsLoading ? (
                  <div className="text-text-secondary text-sm">Loading settings...</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Firm Name</Label>
                      <Input value={settings.firm_name || ''} onChange={e => setSettings(s => ({ ...s, firm_name: e.target.value }))} placeholder="Your Firm LLC" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">EIN</Label>
                      <Input value={settings.firm_ein || ''} onChange={e => setSettings(s => ({ ...s, firm_ein: e.target.value }))} placeholder="XX-XXXXXXX" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div className="md:col-span-2">
                      <Label className="font-sans text-xs text-text-secondary">Address</Label>
                      <Input value={settings.firm_address || ''} onChange={e => setSettings(s => ({ ...s, firm_address: e.target.value }))} placeholder="123 Main St, City, State ZIP" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Phone</Label>
                      <Input value={settings.firm_phone || ''} onChange={e => setSettings(s => ({ ...s, firm_phone: e.target.value }))} placeholder="(555) 123-4567" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Email</Label>
                      <Input type="email" value={settings.firm_email || ''} onChange={e => setSettings(s => ({ ...s, firm_email: e.target.value }))} placeholder="info@yourfirm.com" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Fiscal Year End</Label>
                      <Input value={settings.fiscal_year_end || ''} onChange={e => setSettings(s => ({ ...s, fiscal_year_end: e.target.value }))} placeholder="12/31" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Timezone</Label>
                      <Input value={settings.timezone || ''} onChange={e => setSettings(s => ({ ...s, timezone: e.target.value }))} placeholder="America/New_York" className="bg-canvas border-divider text-sm" />
                    </div>
                    <div>
                      <Label className="font-sans text-xs text-text-secondary">Date Format</Label>
                      <Input value={settings.date_format || ''} onChange={e => setSettings(s => ({ ...s, date_format: e.target.value }))} placeholder="%m/%d/%Y" className="bg-canvas border-divider text-sm" />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Logo Tab */}
          <TabsContent value="logo">
            <Card className="bg-surface border-divider">
              <CardHeader>
                <CardTitle className="font-sans text-sm font-medium text-text-primary">Firm Logo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {settings.logo_path && (
                  <div className="bg-canvas rounded-lg p-6 flex items-center justify-center">
                    <Image size={48} className="text-text-secondary" />
                    <p className="font-mono text-xs text-text-secondary ml-3">{settings.logo_path.split('/').pop()}</p>
                  </div>
                )}
                <div>
                  <Label className="font-sans text-xs text-text-secondary mb-1 block">Upload New Logo (PNG, JPG, GIF, SVG, WebP)</Label>
                  <input type="file" accept=".png,.jpg,.jpeg,.gif,.svg,.webp" onChange={handleLogoUpload} className="text-xs text-text-secondary" />
                </div>
                {logoUploading && <p className="text-text-secondary text-xs">Uploading...</p>}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ML Thresholds Tab */}
          <TabsContent value="thresholds">
            <Card className="bg-surface border-divider">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                    <Shield size={16} className="text-gold" />
                    Recurring Transaction Thresholds
                  </CardTitle>
                  <p className="font-sans text-xs text-text-secondary mt-1">
                    Confidence thresholds for ML-based transaction categorization and auto-confirmation.
                  </p>
                </div>
                <Button size="sm" className="bg-gold text-black hover:bg-gold/90" onClick={handleSaveThresholds} disabled={savingThresholds}>
                  <Save size={14} className="mr-1" /> {savingThresholds ? 'Saving...' : 'Save'}
                </Button>
              </CardHeader>
              <CardContent>
                {thresholdsLoading ? (
                  <div className="text-text-secondary text-sm">Loading thresholds...</div>
                ) : (
                  <div className="space-y-6">
                    {/* High Confidence */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label className="font-sans text-sm text-text-primary">High Confidence</Label>
                        <span className="font-mono text-sm text-emerald-400">{(thresholds.high_confidence * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={thresholds.high_confidence * 100} className="h-2 [&>div]:bg-emerald-400" />
                      <Input
                        type="range"
                        min="0"
                        max="100"
                        value={thresholds.high_confidence * 100}
                        onChange={e => setThresholds(t => ({ ...t, high_confidence: parseInt(e.target.value) / 100 }))}
                        className="mt-2"
                      />
                      <p className="font-sans text-[11px] text-text-secondary mt-1">
                        Transactions above this confidence are considered reliable matches.
                      </p>
                    </div>

                    {/* Medium Confidence */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label className="font-sans text-sm text-text-primary">Medium Confidence</Label>
                        <span className="font-mono text-sm text-amber-400">{(thresholds.medium_confidence * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={thresholds.medium_confidence * 100} className="h-2 [&>div]:bg-amber-400" />
                      <Input
                        type="range"
                        min="0"
                        max="100"
                        value={thresholds.medium_confidence * 100}
                        onChange={e => setThresholds(t => ({ ...t, medium_confidence: parseInt(e.target.value) / 100 }))}
                        className="mt-2"
                      />
                      <p className="font-sans text-[11px] text-text-secondary mt-1">
                        Transactions between medium and high confidence need review.
                      </p>
                    </div>

                    {/* Auto Confirm */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label className="font-sans text-sm text-text-primary">Auto-Confirm Threshold</Label>
                        <span className="font-mono text-sm text-blue-400">{(thresholds.auto_confirm * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={thresholds.auto_confirm * 100} className="h-2 [&>div]:bg-blue-400" />
                      <Input
                        type="range"
                        min="0"
                        max="100"
                        value={thresholds.auto_confirm * 100}
                        onChange={e => setThresholds(t => ({ ...t, auto_confirm: parseInt(e.target.value) / 100 }))}
                        className="mt-2"
                      />
                      <p className="font-sans text-[11px] text-text-secondary mt-1">
                        Transactions at or above this confidence are automatically confirmed.
                      </p>
                    </div>

                    {/* Validation */}
                    {thresholds.high_confidence < thresholds.medium_confidence && (
                      <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-3 rounded-lg border border-red-400/20">
                        <AlertCircle size={14} />
                        High confidence must be {'>= '}Medium confidence
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </section>
  );
}

import React from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, Wrench, Code2, FileJson } from "lucide-react";

interface EndpointInfo {
  method: string;
  path: string;
  description: string;
}

interface PlaceholderPageProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  endpoints?: EndpointInfo[];
}

export default function PlaceholderPage({
  title,
  description,
  icon,
  endpoints = [],
}: PlaceholderPageProps) {
  const navigate = useNavigate();

  return (
    <section className="bg-canvas min-h-[calc(100vh-64px)] px-4 md:px-8 py-8">
      <div className="max-w-[1440px] mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-text-secondary hover:text-gold transition-colors text-sm mb-6"
        >
          <ArrowLeft size={16} />
          Back
        </button>

        <div className="bg-surface border border-divider rounded-xl p-8 md:p-12 text-center max-w-3xl mx-auto">
          <div className="w-16 h-16 rounded-full bg-gold/10 flex items-center justify-center mx-auto mb-6">
            {icon ? (
              <span className="text-gold">{icon}</span>
            ) : (
              <Wrench size={32} className="text-gold" />
            )}
          </div>

          <h1 className="font-serif text-3xl md:text-4xl text-text-primary mb-4">
            {title}
          </h1>
          <p className="font-sans text-text-secondary text-base md:text-lg max-w-xl mx-auto mb-8">
            {description}
          </p>

          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm mb-10">
            <Code2 size={14} />
            Backend endpoints ready — frontend page in progress
          </div>

          {endpoints.length > 0 && (
            <div className="text-left">
              <div className="flex items-center gap-2 mb-4">
                <FileJson size={16} className="text-gold" />
                <h2 className="font-sans text-sm font-medium text-text-primary uppercase tracking-wide">
                  Available API endpoints
                </h2>
              </div>
              <div className="space-y-3">
                {endpoints.map((ep, i) => (
                  <div
                    key={i}
                    className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 p-4 bg-canvas border border-divider rounded-lg"
                  >
                    <div className="flex items-center gap-3 min-w-[220px]">
                      <span className="font-mono text-xs px-2 py-1 rounded bg-gold/10 text-gold">
                        {ep.method}
                      </span>
                      <code className="font-mono text-sm text-text-primary">{ep.path}</code>
                    </div>
                    <p className="font-sans text-sm text-text-secondary">{ep.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

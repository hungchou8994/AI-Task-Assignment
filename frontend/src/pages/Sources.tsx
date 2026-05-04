/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { 
  ExternalLink, 
  FileText, 
  Search, 
  Filter, 
  Calendar,
  Clock,
  Link2,
  Mail,
  ChevronRight,
  Loader2,
  Database
} from 'lucide-react';
import { useProjectContext } from '../context/ProjectContext';
import { useQuery } from '@tanstack/react-query';
import { fetchProjectSources } from '../api/sources';
import { cn } from '../lib/utils';
import { useLanguage } from '../i18n/LanguageContext';

export const SourcesPage = () => {
  const { t } = useLanguage();
  const { currentProjectId } = useProjectContext();
  const sourcesText = (t as {
    sources?: {
      title?: string;
      subtitle?: string;
      loadingSources?: string;
      noSources?: string;
      viewContent?: string;
    };
  }).sources;
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'url' | 'email' | 'text'>('all');

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['sources', currentProjectId],
    queryFn: () => fetchProjectSources(currentProjectId as string),
    enabled: !!currentProjectId,
  });

  const filteredSources = sources.filter(source => {
    const matchesSearch = 
      (source.title?.toLowerCase().includes(searchQuery.toLowerCase()) || false) ||
      (source.uri?.toLowerCase().includes(searchQuery.toLowerCase()) || false) ||
      (source.summary?.toLowerCase().includes(searchQuery.toLowerCase()) || false);
    
    const matchesType = filterType === 'all' || source.source_type === filterType;
    
    return matchesSearch && matchesType;
  });

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="px-8 py-8 border-b border-border bg-card/50">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 text-primary rounded-lg">
              <Database className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">{sourcesText?.title ?? 'Sources'}</h1>
          </div>
          <p className="text-muted-foreground">{sourcesText?.subtitle ?? 'Browse project source inputs.'}</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="px-8 py-4 border-b border-border bg-card/30">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search sources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-background border border-border text-sm focus:ring-1 focus:ring-primary outline-none"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground mr-1" />
            {(['all', 'url', 'email', 'text'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={cn(
                  "px-3 py-1.5 text-xs font-bold uppercase tracking-wider border transition-all",
                  filterType === type 
                    ? "bg-primary text-primary-foreground border-primary" 
                    : "border-border text-muted-foreground hover:bg-muted"
                )}
              >
                {type}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-8">
        <div className="max-w-7xl mx-auto">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
              <p className="text-sm font-medium">{sourcesText?.loadingSources ?? 'Loading sources...'}</p>
            </div>
          ) : filteredSources.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredSources.map((source) => (
                <div 
                  key={source.id}
                  className="bg-card border border-border hover:border-primary/50 transition-all group flex flex-col"
                >
                  <div className="p-5 border-b border-border/50">
                    <div className="flex items-start justify-between mb-4">
                      <div className={cn(
                        "p-2 rounded-lg shrink-0",
                        source.source_type === 'url' ? "bg-blue-500/10 text-blue-500" :
                        source.source_type === 'email' ? "bg-green-500/10 text-green-500" :
                        "bg-muted text-muted-foreground"
                      )}>
                        {source.source_type === 'url' ? <ExternalLink className="w-4 h-4" /> :
                         source.source_type === 'email' ? <Mail className="w-4 h-4" /> :
                         <FileText className="w-4 h-4" />}
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 font-mono">
                        {source.id.slice(0, 8)}
                      </span>
                    </div>
                    
                    <h3 className="font-bold text-foreground mb-1 line-clamp-1 group-hover:text-primary transition-colors">
                      {source.title || (source.source_type === 'url' ? source.uri : 'Untitled Source')}
                    </h3>
                    
                    {source.uri && source.source_type === 'url' && (
                      <a 
                        href={source.uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 mb-2"
                      >
                        <Link2 className="w-3 h-3" />
                        <span className="truncate">{source.uri}</span>
                      </a>
                    )}
                    
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(source.created_at).toLocaleDateString()}
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(source.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                  
                  <div className="p-5 flex-1 bg-muted/5">
                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4 italic">
                      {source.summary || source.excerpt || 'No summary available for this source.'}
                    </p>
                  </div>
                  
                  <div className="px-5 py-4 border-t border-border/50 bg-card flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-primary/5 text-primary text-[10px] font-bold rounded border border-primary/10 uppercase">
                        {source.source_type}
                      </span>
                    </div>
                    <button className="text-xs font-bold text-primary hover:text-primary/80 transition-colors flex items-center gap-1 uppercase tracking-wider">
                      {sourcesText?.viewContent ?? 'View content'}
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground border border-dashed border-border rounded-xl">
              <Database className="w-12 h-12 mb-4 opacity-10" />
              <p className="text-sm font-medium">{sourcesText?.noSources ?? 'No sources found'}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import mermaid from 'mermaid';
import {
  ArrowsOut,
  X,
  MagnifyingGlassPlus,
  MagnifyingGlassMinus,
  ArrowsCounterClockwise,
  DownloadSimple,
} from '@phosphor-icons/react';
import { useThemeTokens } from '../../hooks/useThemeTokens';

interface MermaidViewerProps {
  chart: string;
  title?: string;
}

// Module-level render cache to prevent re-rendering when scrolling or toggling views
const svgCache = new Map<string, string>();

const MermaidViewerComponent: React.FC<MermaidViewerProps> = ({
  chart,
  title = 'Clinical Decision Pathway',
}) => {
  const tokens = useThemeTokens();
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>(() => svgCache.get(chart) || '');
  const [prevChart, setPrevChart] = useState<string>(chart);
  const [hasError, setHasError] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Synchronize state during render if chart prop changes
  if (chart !== prevChart) {
    setPrevChart(chart);
    setSvgContent(svgCache.get(chart) || '');
    setHasError(false);
  }

  // Pan & Zoom states for fullscreen
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const dragStartRef = useRef<{
    x: number;
    y: number;
    panX: number;
    panY: number;
  }>({
    x: 0,
    y: 0,
    panX: 0,
    panY: 0,
  });

  // Stabilize token dependency to prevent unnecessary re-initialization
  const tokenSignature = useMemo(
    () => `${tokens.primary}-${tokens.foreground}-${tokens.card}-${tokens.font}`,
    [tokens.primary, tokens.foreground, tokens.card, tokens.font]
  );

  useEffect(() => {
    // If already in cache, do not re-render
    if (svgCache.has(chart)) {
      return;
    }

    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      securityLevel: 'strict',
      fontFamily: tokens.font || 'system-ui, sans-serif',
      flowchart: {
        htmlLabels: false,
        useMaxWidth: false,
      },
      sequence: {
        useMaxWidth: false,
      },
      themeVariables: {
        primaryColor: tokens.secondary,
        primaryTextColor: tokens.foreground,
        primaryBorderColor: tokens.primary,
        secondaryColor: tokens.card,
        tertiaryColor: tokens.card,
        lineColor: tokens.mutedForeground,
        textColor: tokens.foreground,
        mainBkg: tokens.secondary,
        nodeBorder: tokens.primary,
        clusterBkg: tokens.card,
        clusterBorder: tokens.border,
        edgeLabelBackground: tokens.card,
      },
    });

    let isMounted = true;
    const renderChart = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(id, chart);
        svgCache.set(chart, svg);
        if (isMounted) {
          setSvgContent(svg);
          setHasError(false);
        }
      } catch (err) {
        console.warn('Mermaid render warning:', err);
        if (isMounted) {
          setHasError(true);
        }
      }
    };

    renderChart();
    return () => {
      isMounted = false;
    };
  }, [chart, tokenSignature, tokens]);

  // Handle escape key and body scroll lock for fullscreen modal
  useEffect(() => {
    if (!isFullscreen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreen(false);
      } else if (e.key === '+' || e.key === '=') {
        setZoom((prev) => Math.min(prev + 0.2, 5));
      } else if (e.key === '-') {
        setZoom((prev) => Math.max(prev - 0.2, 0.2));
      } else if (e.key === '0') {
        setZoom(1);
        setPan({ x: 0, y: 0 });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isFullscreen]);

  const openFullscreen = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setIsFullscreen(true);
  };

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.2, 5));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.2, 0.2));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Mouse pan handlers for fullscreen
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    setPan({
      x: dragStartRef.current.panX + dx,
      y: dragStartRef.current.panY + dy,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  // Smooth mouse-wheel zoom for fullscreen
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.15 : -0.15;
    setZoom((prev) => Math.min(Math.max(prev + delta, 0.2), 5));
  };

  // SVG Download
  const handleDownloadSvg = useCallback(() => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], {
      type: 'image/svg+xml;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `clinical-diagram-${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [svgContent]);

  // Robust High-Resolution PNG Download via Canvas
  const handleDownloadPng = useCallback(() => {
    if (!svgContent) return;
    setIsDownloading(true);

    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(svgContent, 'image/svg+xml');
      const svgEl = doc.documentElement;

      // Extract natural dimensions from viewBox or attributes
      let width = parseFloat(svgEl.getAttribute('width') || '0');
      let height = parseFloat(svgEl.getAttribute('height') || '0');
      const viewBox = svgEl.getAttribute('viewBox');

      if (viewBox) {
        const parts = viewBox.split(/[\s,]+/).map(parseFloat);
        if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
          width = parts[2];
          height = parts[3];
        }
      }

      // Check live DOM SVG if viewBox not available or narrow
      const liveSvg = containerRef.current?.querySelector('svg');
      if ((!width || isNaN(width) || width <= 100) && liveSvg) {
        const rect = liveSvg.getBoundingClientRect();
        if (rect.width > 0) width = rect.width;
        if (rect.height > 0) height = rect.height;
      }

      if (isNaN(width) || width <= 0) width = 1200;
      if (isNaN(height) || height <= 0) height = 800;

      // Set explicit attributes so rasterizers don't collapse dimensions
      svgEl.setAttribute('width', `${Math.round(width)}`);
      svgEl.setAttribute('height', `${Math.round(height)}`);
      svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      svgEl.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

      // 2x Retina scaling for ultra crisp diagram text
      const scale = 2;
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        setIsDownloading(false);
        return;
      }

      const serialized = new XMLSerializer().serializeToString(svgEl);
      // Use data URL with encodeURIComponent to ensure instant local loading without CORS/blob taint
      const svgDataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serialized);
      const img = new Image();

      img.onload = () => {
        try {
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

          canvas.toBlob((blob) => {
            if (!blob) {
              const pngUrl = canvas.toDataURL('image/png');
              const link = document.createElement('a');
              link.href = pngUrl;
              link.download = `clinical-diagram-${Date.now()}.png`;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              setIsDownloading(false);
              return;
            }
            const blobUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = `clinical-diagram-${Date.now()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(blobUrl);
            setIsDownloading(false);
          }, 'image/png');
        } catch (err) {
          console.error('Canvas export failed, falling back to SVG:', err);
          setIsDownloading(false);
          handleDownloadSvg();
        }
      };

      img.onerror = (e) => {
        console.error('Image rasterization failed, falling back to SVG:', e);
        setIsDownloading(false);
        handleDownloadSvg();
      };

      img.src = svgDataUrl;
    } catch (e) {
      console.error('PNG export failed, falling back to SVG:', e);
      setIsDownloading(false);
      handleDownloadSvg();
    }
  }, [svgContent, handleDownloadSvg]);

  if (hasError) {
    return (
      <div className="bg-muted p-3 rounded-xl border border-border text-xs text-muted-foreground font-mono overflow-x-auto my-3">
        {chart}
      </div>
    );
  }

  return (
    <>
      {/* Inline Diagram Card - Stable, performant & smooth scrolling without hover transforms */}
      <div
        className="relative bg-card p-4 rounded-xl border border-border my-3 shadow-xs overflow-hidden"
        style={{ contain: 'paint' }}
      >
        {/* Header Toolbar */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-border/60">
          <span className="text-xs font-semibold text-primary uppercase tracking-wider flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-primary/70" />
            {title}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleDownloadPng}
              disabled={isDownloading || !svgContent}
              title="Download diagram as high-resolution PNG"
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-muted-foreground hover:text-foreground bg-muted/60 hover:bg-muted border border-border/50 transition-colors cursor-pointer"
            >
              <DownloadSimple size={13} weight="bold" />
              <span>{isDownloading ? 'Exporting…' : 'PNG'}</span>
            </button>
            <button
              type="button"
              onClick={handleDownloadSvg}
              disabled={!svgContent}
              title="Download diagram as vector SVG"
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-muted-foreground hover:text-foreground bg-muted/60 hover:bg-muted border border-border/50 transition-colors cursor-pointer"
            >
              <DownloadSimple size={13} weight="bold" />
              <span>SVG</span>
            </button>
            <button
              type="button"
              onClick={openFullscreen}
              title="View fullscreen with pan and zoom"
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-primary hover:text-primary-foreground bg-primary/10 hover:bg-primary border border-primary/20 transition-colors cursor-pointer shadow-2xs"
            >
              <ArrowsOut size={13} weight="bold" />
              <span>Fullscreen</span>
            </button>
          </div>
        </div>

        {/* Stable Diagram Canvas Container - No hover zoom/scale to prevent scrolling lag/glitches */}
        <div
          role="button"
          tabIndex={0}
          onClick={openFullscreen}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              openFullscreen();
            }
          }}
          title="Click to view fullscreen, move and zoom"
          className="cursor-pointer overflow-x-auto flex justify-center py-2"
        >
          <div
            ref={containerRef}
            dangerouslySetInnerHTML={{ __html: svgContent }}
            className="w-full flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
          />
        </div>
      </div>

      {/* Clean Fullscreen Modal with Free Pan & Zoom */}
      {isFullscreen &&
        createPortal(
          <div
            className="fixed inset-0 z-[9999] bg-black/90 backdrop-blur-sm flex flex-col select-none animate-in fade-in duration-150"
            role="dialog"
            aria-modal="true"
          >
            {/* Minimal Header Controls */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-black/40 text-white">
              <h3 className="text-sm font-medium tracking-wide text-white/90">{title}</h3>

              <div className="flex items-center gap-2">
                {/* Zoom controls */}
                <div className="flex items-center bg-white/10 rounded-lg p-0.5 border border-white/10">
                  <button
                    type="button"
                    onClick={handleZoomOut}
                    title="Zoom out (-)"
                    className="p-1.5 text-white/70 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer"
                  >
                    <MagnifyingGlassMinus size={16} weight="bold" />
                  </button>
                  <span className="text-xs font-mono font-medium px-2.5 min-w-14 text-center text-white">
                    {Math.round(zoom * 100)}%
                  </span>
                  <button
                    type="button"
                    onClick={handleZoomIn}
                    title="Zoom in (+)"
                    className="p-1.5 text-white/70 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer"
                  >
                    <MagnifyingGlassPlus size={16} weight="bold" />
                  </button>
                  <button
                    type="button"
                    onClick={handleReset}
                    title="Reset view (0)"
                    className="p-1.5 text-white/70 hover:text-white rounded-md hover:bg-white/10 border-l border-white/10 transition-colors cursor-pointer ml-1"
                  >
                    <ArrowsCounterClockwise size={14} weight="bold" />
                  </button>
                </div>

                {/* Downloads */}
                <button
                  type="button"
                  onClick={handleDownloadPng}
                  disabled={isDownloading}
                  title="Download as PNG"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-white bg-white/10 hover:bg-white/20 border border-white/15 transition-all cursor-pointer"
                >
                  <DownloadSimple size={14} weight="bold" />
                  <span>{isDownloading ? 'Exporting…' : 'Download PNG'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleDownloadSvg}
                  title="Download as SVG"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-white bg-white/10 hover:bg-white/20 border border-white/15 transition-all cursor-pointer"
                >
                  <DownloadSimple size={14} weight="bold" />
                  <span>Download SVG</span>
                </button>

                {/* Close */}
                <button
                  type="button"
                  onClick={() => setIsFullscreen(false)}
                  title="Close (Esc)"
                  className="p-1.5 ml-2 text-white/70 hover:text-white hover:bg-white/20 rounded-lg border border-white/15 transition-colors cursor-pointer"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>
            </div>

            {/* Pannable Canvas Area */}
            <div
              className={`flex-1 relative overflow-hidden flex items-center justify-center ${
                isDragging ? 'cursor-grabbing' : 'cursor-grab'
              }`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
              onDoubleClick={handleReset}
              title="Click & drag to move around. Scroll to zoom in/out."
            >
              <div
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                  transformOrigin: 'center center',
                  transition: isDragging ? 'none' : 'transform 0.08s ease-out',
                }}
                dangerouslySetInnerHTML={{ __html: svgContent }}
                className="max-w-none max-h-none pointer-events-none drop-shadow-2xl select-none [&_svg]:max-w-none [&_svg]:h-auto"
              />
            </div>
          </div>,
          document.body
        )}
    </>
  );
};

export const MermaidViewer = React.memo(MermaidViewerComponent);

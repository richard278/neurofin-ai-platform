import { useState, useEffect, useRef } from 'react';
import { useForecastMutation } from '../hooks/useForecastMutation';

interface Preset {
  id: string;
  name: string;
  symbol: string;
  horizon: number;
  values: number[];
  description: string;
}

const PRESETS: Preset[] = [
  {
    id: 'delinquency',
    name: 'MFI Delinquency Ratio',
    symbol: 'SLV_DELINQ_RATIO',
    horizon: 12,
    values: [2.3, 2.5, 2.8, 3.1, 3.0, 3.4, 3.2, 3.5, 3.8, 4.1, 4.0, 4.3],
    description: 'Salvadoran Microfinance delinquency indicator (last 12 months, %)',
  },
  {
    id: 'default_rate',
    name: 'KrediSense Defaults',
    symbol: 'KREDISENSE_DEFAULTS',
    horizon: 24,
    values: [0.045, 0.048, 0.052, 0.050, 0.055, 0.058, 0.062, 0.065, 0.070, 0.075, 0.082, 0.080],
    description: 'KrediSense active credit portfolios default ratio',
  },
  {
    id: 'compound_interest',
    name: 'Compound Accrual Trend',
    symbol: 'COMP_INT_ACC',
    horizon: 12,
    values: [100.0, 102.5, 105.06, 107.69, 110.38, 113.14, 115.97, 118.87, 121.84, 124.89, 128.01, 131.21],
    description: 'Simulated compound interest growth series',
  },
  {
    id: 'custom',
    name: 'Custom Series / Manual',
    symbol: 'CUSTOM_ASSET',
    horizon: 12,
    values: [],
    description: 'Enter your own data series below',
  },
];

interface TooltipState {
  index: number;
  x: number;
  y: number;
  value: number;
  isForecast: boolean;
  stepLabel: string;
}

function renderApiError(error: any) {
  if (!error) return null;
  const details = error.details;

  if (details && details.detail) {
    if (Array.isArray(details.detail)) {
      return (
        <ul className="api-error-list" style={{ margin: 0, paddingLeft: 'var(--space-4)', fontSize: '0.875rem' }}>
          {details.detail.map((err: any, idx: number) => {
            const path = Array.isArray(err.loc) ? err.loc.filter((loc: any) => loc !== 'body').join('.') : '';
            return (
              <li key={idx} style={{ marginTop: 'var(--space-1)' }}>
                {path ? <strong>{path}: </strong> : null}
                {err.msg}
              </li>
            );
          })}
        </ul>
      );
    }
    if (typeof details.detail === 'string') {
      return details.detail;
    }
  }
  return error.message || 'An error occurred while contacting the forecast API. Check your local backend connection.';
}

export function ForecastPage() {
  const mutation = useForecastMutation();

  const [activePreset, setActivePreset] = useState<string>('delinquency');
  const [symbol, setSymbol] = useState<string>('SLV_DELINQ_RATIO');
  const [horizon, setHorizon] = useState<number>(12);
  const [historicalText, setHistoricalText] = useState<string>(
    '2.3, 2.5, 2.8, 3.1, 3.0, 3.4, 3.2, 3.5, 3.8, 4.1, 4.0, 4.3'
  );
  const [validationError, setValidationError] = useState<string | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<TooltipState | null>(null);

  const chartCardRef = useRef<HTMLDivElement>(null);

  // Load preset details
  const handlePresetSelect = (preset: Preset) => {
    setActivePreset(preset.id);
    setSymbol(preset.symbol);
    setHorizon(preset.horizon);
    if (preset.id !== 'custom') {
      setHistoricalText(preset.values.join(', '));
      setValidationError(null);
    }
  };

  // Run forecast automatically for the default preset on first load
  useEffect(() => {
    const defaultPreset = PRESETS[0];
    mutation.mutate({
      symbol: defaultPreset.symbol,
      horizon: defaultPreset.horizon,
      historical_values: defaultPreset.values,
    });
  }, []);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setHistoricalText(e.target.value);
    setActivePreset('custom');
    setValidationError(null);
  };

  const parseHistoricalValues = (text: string): number[] => {
    return text
      .split(/[\s,;\n]+/)
      .map((val) => val.trim())
      .filter((val) => val.length > 0)
      .map((val) => {
        const parsed = parseFloat(val);
        if (isNaN(parsed)) {
          throw new Error(`"${val}" is not a valid number.`);
        }
        return parsed;
      });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setHoveredPoint(null);

    if (!symbol.trim()) {
      setValidationError('Symbol / Ticker identifier is required.');
      return;
    }

    try {
      const parsedValues = parseHistoricalValues(historicalText);
      if (parsedValues.length === 0) {
        setValidationError('At least one historical data point must be provided.');
        return;
      }

      mutation.mutate({
        symbol: symbol.trim().toUpperCase(),
        horizon: horizon,
        historical_values: parsedValues,
      });
    } catch (err: any) {
      setValidationError(err.message || 'Invalid historical values.');
    }
  };

  // Calculate stats for loaded forecast
  const getForecastStats = (history: number[], result: any) => {
    if (!history || history.length === 0 || !result.points || result.points.length === 0) {
      return { lastVal: 0, forecastEnd: 0, pctChange: 0, meanVal: 0 };
    }
    const lastVal = history[history.length - 1];
    const forecastEnd = result.points[result.points.length - 1].value;
    const meanVal = result.points[0].value;
    const pctChange = lastVal !== 0 ? ((forecastEnd - lastVal) / lastVal) * 100 : 0;

    return { lastVal, forecastEnd, pctChange, meanVal };
  };

  // Rendering Helper: Custom Interactive SVG Chart
  const renderSvgChart = (history: number[], result: any) => {
    const nHistory = history.length;
    const nForecast = result.points.length;
    const totalPoints = nHistory + nForecast;

    // Combine data points
    const combinedPoints = [
      ...history.map((val, idx) => ({
        value: val,
        isForecast: false,
        label: `t - ${nHistory - 1 - idx}`,
        index: idx,
      })),
      ...result.points.map((p: any, idx: number) => ({
        value: p.value,
        isForecast: true,
        label: `t + ${p.step}`,
        index: nHistory + idx,
      })),
    ];

    // Find min and max for Y scaling
    const values = combinedPoints.map((p) => p.value);
    let yMin = Math.min(...values);
    let yMax = Math.max(...values);

    // Padding buffer
    const buffer = (yMax - yMin) * 0.1 || 1.0;
    yMin -= buffer;
    yMax += buffer;

    // SVG Dimensions
    const svgWidth = 800;
    const svgHeight = 350;
    const padLeft = 60;
    const padRight = 30;
    const padTop = 30;
    const padBottom = 40;

    const plotWidth = svgWidth - padLeft - padRight;
    const plotHeight = svgHeight - padTop - padBottom;

    // Scale helpers
    const getX = (index: number) => padLeft + (index / (totalPoints - 1)) * plotWidth;
    const getY = (val: number) => svgHeight - padBottom - ((val - yMin) / (yMax - yMin)) * plotHeight;

    // Build line pathways
    let historyPath = '';
    if (nHistory > 0) {
      historyPath = `M ${getX(0)} ${getY(history[0])}`;
      for (let i = 1; i < nHistory; i++) {
        historyPath += ` L ${getX(i)} ${getY(history[i])}`;
      }
    }

    let forecastPath = '';
    if (nForecast > 0 && nHistory > 0) {
      forecastPath = `M ${getX(nHistory - 1)} ${getY(history[nHistory - 1])}`;
      for (let i = 0; i < nForecast; i++) {
        forecastPath += ` L ${getX(nHistory + i)} ${getY(result.points[i].value)}`;
      }
    }

    // Gradient Area pathways
    let historyArea = '';
    if (nHistory > 0) {
      historyArea = `${historyPath} L ${getX(nHistory - 1)} ${getY(yMin)} L ${getX(0)} ${getY(yMin)} Z`;
    }

    let forecastArea = '';
    if (nForecast > 0 && nHistory > 0) {
      forecastArea = `${forecastPath} L ${getX(nHistory + nForecast - 1)} ${getY(yMin)} L ${getX(nHistory - 1)} ${getY(yMin)} Z`;
    }

    // Grid ticks (4 steps)
    const yTicks = 4;
    const gridLines = Array.from({ length: yTicks + 1 }).map((_, idx) => {
      const val = yMin + (idx / yTicks) * (yMax - yMin);
      return { val, y: getY(val) };
    });

    const handleMouseMove = (e: React.MouseEvent<SVGCircleElement>, point: typeof combinedPoints[0]) => {
      if (!chartCardRef.current) return;
      const relativeX = getX(point.index);
      const relativeY = getY(point.value);

      setHoveredPoint({
        index: point.index,
        x: relativeX,
        y: relativeY,
        value: point.value,
        isForecast: point.isForecast,
        stepLabel: point.label,
      });
    };

    return (
      <div className="chart-card" ref={chartCardRef}>
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="chart-svg">
          <defs>
            <linearGradient id="historyGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0FA47A" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#0FA47A" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {gridLines.map((line, idx) => (
            <g key={idx}>
              <line
                x1={padLeft}
                y1={line.y}
                x2={svgWidth - padRight}
                y2={line.y}
                className="chart-grid-line"
              />
              <text
                x={padLeft - 10}
                y={line.y + 4}
                textAnchor="end"
                className="chart-label"
              >
                {line.val.toFixed(2)}
              </text>
            </g>
          ))}

          {/* Transition dotted split line */}
          {nHistory > 0 && (
            <g>
              <line
                x1={getX(nHistory - 1)}
                y1={padTop}
                x2={getX(nHistory - 1)}
                y2={svgHeight - padBottom}
                className="chart-split-line"
              />
              <text
                x={getX(nHistory - 1)}
                y={padTop - 8}
                textAnchor="middle"
                fill="#f59e0b"
                fontSize="9px"
                fontWeight="700"
                letterSpacing="0.05em"
              >
                FORECAST ORIGIN
              </text>
            </g>
          )}

          {/* Area Gradients */}
          {historyArea && <path d={historyArea} className="chart-area-history" />}
          {forecastArea && <path d={forecastArea} className="chart-area-forecast" />}

          {/* Line paths */}
          {historyPath && <path d={historyPath} className="chart-path-history" />}
          {forecastPath && <path d={forecastPath} className="chart-path-forecast" />}

          {/* X Axis label */}
          <line
            x1={padLeft}
            y1={svgHeight - padBottom}
            x2={svgWidth - padRight}
            y2={svgHeight - padBottom}
            className="chart-axis-line"
          />

          <text
            x={padLeft}
            y={svgHeight - padBottom + 18}
            textAnchor="start"
            className="chart-label"
          >
            {combinedPoints[0]?.label || ''}
          </text>
          {nHistory > 0 && (
            <text
              x={getX(nHistory - 1)}
              y={svgHeight - padBottom + 18}
              textAnchor="middle"
              className="chart-label"
              fontWeight="bold"
            >
              Origin
            </text>
          )}
          <text
            x={svgWidth - padRight}
            y={svgHeight - padBottom + 18}
            textAnchor="end"
            className="chart-label"
          >
            {combinedPoints[combinedPoints.length - 1]?.label || ''}
          </text>

          {/* Hotspot circle markers for mouse interaction */}
          {combinedPoints.map((point) => (
            <circle
              key={point.index}
              cx={getX(point.index)}
              cy={getY(point.value)}
              r={hoveredPoint?.index === point.index ? 6 : 4}
              fill={point.isForecast ? '#0FA47A' : '#3b82f6'}
              stroke="#0f172a"
              strokeWidth={hoveredPoint?.index === point.index ? 2 : 1}
              className="chart-point-marker"
              onMouseMove={(e) => handleMouseMove(e, point)}
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}
        </svg>

        {/* Hover Tooltip */}
        {hoveredPoint && (
          <div
            className="chart-tooltip-floating"
            style={{
              left: `${(hoveredPoint.x / svgWidth) * 100}%`,
              top: `${hoveredPoint.y - 65}px`,
              transform: 'translateX(-50%)',
            }}
          >
            <div className="chart-tooltip-title">{hoveredPoint.stepLabel}</div>
            <div className="chart-tooltip-value">{hoveredPoint.value.toFixed(4)}</div>
            <div
              className={`chart-tooltip-type chart-tooltip-type--${
                hoveredPoint.isForecast ? 'forecast' : 'history'
              }`}
            >
              {hoveredPoint.isForecast ? 'Forecast (SMA)' : 'Historical'}
            </div>
          </div>
        )}
      </div>
    );
  };

  const parsedHistoryValues = () => {
    try {
      return parseHistoricalValues(historicalText);
    } catch {
      return [];
    }
  };

  const historyPoints = parsedHistoryValues();
  const { lastVal, forecastEnd, pctChange, meanVal } =
    mutation.data ? getForecastStats(historyPoints, mutation.data) : { lastVal: 0, forecastEnd: 0, pctChange: 0, meanVal: 0 };

  return (
    <div className="page-stack">
      {/* Title block */}
      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="panel__eyebrow">Interactive Engine</p>
            <h2 className="panel__title">Run and Analyze Asset Forecasts</h2>
          </div>
        </div>
        <p className="muted">
          Execute automated statistical moving average projections on credit risk, delinquency data, or simulated financial time-series. Select a preset below or supply a custom CSV series.
        </p>
      </section>

      {/* Main Grid layout */}
      <div className="forecast-placeholder">
        {/* Left Side: Parameters Form */}
        <section className="panel">
          <h3 className="panel__title" style={{ fontSize: '1.2rem', marginBottom: 'var(--space-4)' }}>
            Parameters
          </h3>

          <div className="form-group">
            <span className="form-label">Data Presets</span>
            <div className="preset-grid">
              {PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handlePresetSelect(preset)}
                  className={`preset-btn ${activePreset === preset.id ? 'preset-btn--active' : ''}`}
                >
                  {preset.name}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="page-stack" style={{ gap: 'var(--space-4)' }}>
            <div className="form-group">
              <label htmlFor="symbol-input" className="form-label">
                Asset Symbol / Identifier
              </label>
              <input
                id="symbol-input"
                type="text"
                value={symbol}
                onChange={(e) => {
                  setSymbol(e.target.value);
                  setActivePreset('custom');
                }}
                className="form-input"
                placeholder="e.g. SLV_DELINQ_RATIO"
              />
            </div>

            <div className="form-group">
              <label htmlFor="horizon-input" className="form-label">
                Forecast Horizon (Periods): <strong>{horizon}</strong>
              </label>
              <input
                id="horizon-input"
                type="range"
                min="1"
                max="120"
                value={horizon}
                onChange={(e) => {
                  setHorizon(parseInt(e.target.value));
                  setActivePreset('custom');
                }}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </div>

            <div className="form-group">
              <label htmlFor="historical-input" className="form-label">
                Historical Series (Comma separated)
              </label>
              <textarea
                id="historical-input"
                value={historicalText}
                onChange={handleTextChange}
                className="form-textarea"
                placeholder="e.g. 2.1, 2.3, 2.6, 2.8..."
              />
              <span className="muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                Separate numbers using commas, spaces, or lines. Supports copy-paste.
              </span>
            </div>

            {validationError && (
              <div className="alert-error">
                <p>{validationError}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={mutation.isPending}
              className="btn-primary"
              style={{ width: '100%', marginTop: 'var(--space-2)' }}
            >
              {mutation.isPending ? 'Generating Forecast...' : 'Execute Forecast'}
            </button>
          </form>
        </section>

        {/* Right Side: Results Display */}
        <section className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          <h3 className="panel__title" style={{ fontSize: '1.2rem', marginBottom: '0' }}>
            Forecast Projections
          </h3>

          {/* Loading Skeleton */}
          {mutation.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', width: '100%', flex: 1, justifyContent: 'center' }}>
              <div className="hero__grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                <div className="skeleton-bar" style={{ height: '70px' }}></div>
                <div className="skeleton-bar" style={{ height: '70px' }}></div>
                <div className="skeleton-bar" style={{ height: '70px' }}></div>
              </div>
              <div className="skeleton-bar" style={{ height: '240px', width: '100%' }}></div>
            </div>
          )}

          {/* Error Alert */}
          {mutation.isError && (
            <div className="alert-error" style={{ margin: 'auto 0' }}>
              <h4 style={{ margin: '0 0 var(--space-2)' }}>Backend API Error</h4>
              <div style={{ marginTop: 'var(--space-1)' }}>
                {renderApiError(mutation.error)}
              </div>
            </div>
          )}

          {/* Ideal view (No data run) */}
          {!mutation.isPending && !mutation.isError && !mutation.data && (
            <div className="muted" style={{ margin: 'auto', textAlign: 'center', padding: 'var(--space-8) 0' }}>
              <p>Configure parameters on the left and click "Execute Forecast" to see outputs.</p>
            </div>
          )}

          {/* Success / Visual Results view */}
          {!mutation.isPending && !mutation.isError && mutation.data && (
            <>
              {/* Metric Cards Summary */}
              <div className="hero__grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
                <div className="metric-card" style={{ padding: 'var(--space-4)' }}>
                  <p className="metric-card__label">Origin Value</p>
                  <p className="metric-card__value" style={{ fontSize: '1.5rem', color: '#60a5fa' }}>
                    {lastVal.toFixed(3)}
                  </p>
                  <p className="metric-card__description" style={{ fontSize: '0.75rem' }}>
                    Last historical observation
                  </p>
                </div>

                <div className="metric-card" style={{ padding: 'var(--space-4)' }}>
                  <p className="metric-card__label">Projected Mean</p>
                  <p className="metric-card__value" style={{ fontSize: '1.5rem', color: 'var(--success)' }}>
                    {meanVal.toFixed(3)}
                  </p>
                  <p className="metric-card__description" style={{ fontSize: '0.75rem' }}>
                    Moving Average estimate
                  </p>
                </div>

                <div className="metric-card" style={{ padding: 'var(--space-4)' }}>
                  <p className="metric-card__label">Expected Delta</p>
                  <p
                    className="metric-card__value"
                    style={{
                      fontSize: '1.5rem',
                      color: pctChange > 0 ? 'var(--warning)' : pctChange < 0 ? '#ef4444' : 'var(--text-soft)',
                    }}
                  >
                    {pctChange > 0 ? '+' : ''}
                    {pctChange.toFixed(2)}%
                  </p>
                  <p className="metric-card__description" style={{ fontSize: '0.75rem' }}>
                    Projection change vs. origin
                  </p>
                </div>
              </div>

              {/* The SVG Chart */}
              {renderSvgChart(historyPoints, mutation.data)}

              {/* Detailed Points Table */}
              <div>
                <h4 className="form-label" style={{ marginBottom: 'var(--space-2)' }}>
                  Detailed Projections table
                </h4>
                <div className="results-table-container">
                  <table className="results-table">
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Type</th>
                        <th>Projected Value</th>
                        <th>Delta vs Origin</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mutation.data.points.map((pt: any) => {
                        const valDelta = pt.value - lastVal;
                        const pctDelta = lastVal !== 0 ? (valDelta / lastVal) * 100 : 0;
                        return (
                          <tr key={pt.step}>
                            <td>t + {pt.step}</td>
                            <td>
                              <span style={{ color: 'var(--success)', fontWeight: 'bold' }}>
                                Forecast
                              </span>
                            </td>
                            <td>{pt.value.toFixed(4)}</td>
                            <td
                              style={{
                                color: valDelta > 0 ? '#f59e0b' : valDelta < 0 ? '#ef4444' : 'inherit',
                                fontWeight: '500',
                              }}
                            >
                              {valDelta > 0 ? '+' : ''}
                              {valDelta.toFixed(4)} ({pctDelta > 0 ? '+' : ''}
                              {pctDelta.toFixed(2)}%)
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}


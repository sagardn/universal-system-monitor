import { useChannel } from '../hooks/useChannel'
import { CardSkeleton } from '../components/Skeleton'

export default function Security() {
  const { data, loading } = useChannel('security')

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(4)].map((_,i) => <CardSkeleton key={i} />)}</div>

  if (!data) return <div className="glass p-10 text-center"><p className="text-txt-muted">No security data available</p></div>

  // security_score can be a dict {score, grade, issues} or a plain number
  const scoreData = data.security_score
  const score = typeof scoreData === 'number' ? scoreData : (scoreData?.score ?? 0)
  const grade = (typeof scoreData === 'object' && scoreData?.grade) ? String(scoreData.grade) : (score >= 80 ? 'A' : score >= 60 ? 'B' : score >= 40 ? 'C' : score >= 20 ? 'D' : 'F')
  const gradeColor = score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-danger'
  const scoreIssues = (typeof scoreData === 'object' && Array.isArray(scoreData?.issues)) ? scoreData.issues : []
  const firewall = (data.firewall && typeof data.firewall === 'object') ? data.firewall : {}
  const logins = Array.isArray(data.failed_logins) ? data.failed_logins : []
  const ports = Array.isArray(data.open_ports) ? data.open_ports : []
  const summary = (data.summary && typeof data.summary === 'object') ? data.summary : {}

  return (
    <div>
      {/* Score */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="glass p-5 text-center">
          <div className={`text-4xl font-bold ${gradeColor}`}>{String(grade)}</div>
          <div className="text-xs text-txt-muted mt-1">Score: {String(score)}/100</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Firewall</div>
          <div className={`font-bold text-base mt-1 ${firewall.active ? 'text-success' : 'text-danger'}`}>
            {firewall.active ? '🛡️ Active' : '⚠️ Inactive'}
          </div>
          <div className="text-xs text-txt-muted mt-1">{String(firewall.type || firewall.name || 'Unknown')}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Failed Logins</div>
          <div className={`font-bold text-base mt-1 ${logins.length > 5 ? 'text-danger' : 'text-txt'}`}>{String(logins.length)}</div>
          <div className="text-xs text-txt-muted mt-1">Recent</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.6875rem] text-txt-muted uppercase tracking-wider font-semibold">Open Ports</div>
          <div className="font-bold text-base mt-1">{String(ports.length)}</div>
          <div className="text-xs text-txt-muted mt-1">{String(ports.length)} total</div>
        </div>
      </div>

      {/* Security Issues */}
      {scoreIssues.length > 0 && (
        <div className="flex gap-2 mb-4 flex-wrap">
          {scoreIssues.map((issue, i) => (
            <span key={i} className="inline-flex items-center px-2.5 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-warning-muted text-warning">
              ⚠ {String(issue)}
            </span>
          ))}
        </div>
      )}

      {/* Failed logins */}
      {logins.length > 0 && (
        <div className="glass p-0 overflow-hidden mb-4">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Recent Failed Logins
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {logins.slice(0, 20).map((l, i) => (
              <div key={i} className="flex items-center gap-3 py-2 px-4 border-b border-border last:border-0 text-xs">
                <span className="text-danger font-semibold">{String(l.service || '')}</span>
                <span className="text-txt-muted">{String(l.user || '')}@{String(l.source || '')}</span>
                <span className="ml-auto text-txt-muted">{String(l.time || '')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Open ports */}
      {ports.length > 0 && (
        <div className="glass p-0 overflow-hidden">
          <div className="text-xs font-semibold text-txt-muted uppercase tracking-wider py-2 px-4 bg-bg-surface">
            Open Ports
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            <table className="dtable">
              <thead><tr><th>Port</th><th>Protocol</th><th>Bind</th><th>Process</th><th>PID</th><th>Service</th></tr></thead>
              <tbody>
                {ports.map((p, i) => (
                  <tr key={i}>
                    <td className="tabular-nums font-semibold">{String(p.port ?? '—')}</td>
                    <td>{String(p.protocol || '')}</td>
                    <td className="text-txt-muted">{String(p.bind || '')}</td>
                    <td className="font-medium">{String(p.process || '—')}</td>
                    <td className="tabular-nums text-txt-muted">{String(p.pid || '—')}</td>
                    <td>
                      {p.known_service ? (
                        <span className="inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-primary-muted text-primary">
                          {String(p.known_service)}
                        </span>
                      ) : p.is_expected ? (
                        <span className="text-txt-muted">expected</span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 text-[0.6875rem] font-semibold rounded-full bg-warning-muted text-warning">
                          unknown
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Skeleton({ w = '100%', h = 14, circle = false, count = 1 }) {
  const style = {
    width: circle ? h : w,
    height: h,
    borderRadius: circle ? '50%' : undefined,
    marginBottom: count > 1 ? 8 : 0,
  }
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton" style={style} />
      ))}
    </>
  )
}

export function CardSkeleton() {
  return (
    <div className="card" style={{ minHeight: 120 }}>
      <Skeleton w="40%" h={14} />
      <div style={{ marginTop: 12 }}>
        <Skeleton w="60%" h={28} />
      </div>
      <div style={{ marginTop: 12 }}>
        <Skeleton w="100%" h={10} />
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 8, cols = 6 }) {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
        <Skeleton w="200px" h={14} />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} style={{ display: 'flex', gap: 16, padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
          {Array.from({ length: cols }, (_, j) => (
            <Skeleton key={j} w={j === 1 ? '30%' : '12%'} h={12} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function GaugeSkeleton() {
  return (
    <div className="gauge-wrap">
      <Skeleton circle h={120} />
      <Skeleton w="60px" h={12} />
    </div>
  )
}

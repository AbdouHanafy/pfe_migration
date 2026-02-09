const Card = ({ title, hint, actions, children, className = '' }) => {
  return (
    <section className={`panel ${className}`}>
      {title ? <h2>{title}</h2> : null}
      {hint ? <p className="hint">{hint}</p> : null}
      {actions ? <div className="row">{actions}</div> : null}
      {children}
    </section>
  )
}

export default Card

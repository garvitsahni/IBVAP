export default function Card({ title, eyebrow, children, footer }) {
  return (
    <div className="card">
      {eyebrow && <div className="card__eyebrow">{eyebrow}</div>}
      {title && <h3 className="card__title">{title}</h3>}
      <div className="card__body">{children}</div>
      {footer && <div className="card__footer">{footer}</div>}
    </div>
  );
}

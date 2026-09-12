import { Link } from "react-router-dom";
import "./Button.css";

export default function Button({
  children,
  to,
  variant = "primary",
  type = "button",
  onClick,
  disabled = false,
  fullWidth = false,
}) {
  const className = `btn btn--${variant}${fullWidth ? " btn--full" : ""}`;

  if (to) {
    return (
      <Link to={to} className={className}>
        {children}
      </Link>
    );
  }

  return (
    <button type={type} className={className} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

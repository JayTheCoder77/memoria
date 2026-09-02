import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "google";

const variants: Record<Variant, string> = {
  primary: "btn-cut bg-accent text-bg-terminal",
  secondary: "btn-cut border border-text-primary bg-transparent text-text-primary",
  ghost: "border border-border-subtle bg-transparent text-text-secondary",
  danger: "border border-danger bg-transparent text-danger",
  google: "bg-text-primary text-bg-terminal",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  href?: string;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  href,
  className = "",
  children,
  ...props
}: Props) {
  const classes = `inline-flex h-11 items-center justify-center px-5 text-sm font-medium ${variants[variant]} ${className}`;
  if (href) {
    return (
      <Link className={classes} href={href}>
        {children}
      </Link>
    );
  }
  return (
    <button className={classes} type={props.type ?? "button"} {...props}>
      {children}
    </button>
  );
}

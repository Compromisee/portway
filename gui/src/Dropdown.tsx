import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";

export type DropdownOption = {
  id: string;
  label: string;
  hint?: string;
};

type Props = {
  value: string;
  options: DropdownOption[];
  onChange: (id: string) => void;
  label: string;
  wide?: boolean;
};

export function Dropdown({ value, options, onChange, label, wide }: Props) {
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState({ top: 0, left: 0, width: 180 });
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  const current = options.find((item) => item.id === value) || options[0];

  const place = () => {
    const el = root.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.max(rect.width, wide ? 220 : 180);
    let left = rect.left;
    if (left + width > window.innerWidth - 12) {
      left = Math.max(12, window.innerWidth - width - 12);
    }
    let top = rect.bottom + 6;
    const menuHeight = menu.current?.offsetHeight || options.length * 52 + 12;
    if (top + menuHeight > window.innerHeight - 12) {
      top = Math.max(12, rect.top - menuHeight - 6);
    }
    setBox({ top, left, width });
  };

  useLayoutEffect(() => {
    if (!open) return;
    place();
  }, [open, wide, options.length]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (root.current?.contains(target) || menu.current?.contains(target)) return;
      setOpen(false);
    };
    const onScroll = () => place();
    document.addEventListener("mousedown", close);
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);

  return (
    <div className={`dd ${wide ? "dd-wide" : ""}`} ref={root}>
      <button
        type="button"
        className="dd-btn"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((was) => !was)}
      >
        <span className="dd-text">
          <span className="dd-kicker">{label}</span>
          <span className="dd-value">{current?.label}</span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 ${open ? "rotate-180" : ""}`} />
      </button>
      {open
        ? createPortal(
            <ul
              ref={menu}
              className="dd-menu"
              role="listbox"
              style={{ top: box.top, left: box.left, width: box.width }}
            >
              {options.map((option) => (
                <li key={option.id} role="option" aria-selected={option.id === value}>
                  <button
                    type="button"
                    className={option.id === value ? "on" : ""}
                    onClick={() => {
                      onChange(option.id);
                      setOpen(false);
                    }}
                  >
                    <span>{option.label}</span>
                    {option.hint ? <small>{option.hint}</small> : null}
                  </button>
                </li>
              ))}
            </ul>,
            document.body,
          )
        : null}
    </div>
  );
}

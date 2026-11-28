// Quoted words found in a fragment's text as `quoteOf` reads a selection: whitespace collapsed, a formula or a command whole as its TeX.
import { describe, expect, it } from "vitest";
import { findIn, mathText, type MathNode, type Piece } from "./quote";

const t = (text: string): Piece => ({ text, atom: false });
const tex = (text: string): Piece => ({ text, atom: true });

describe("quoted words in a fragment", () => {
  it("are found across text nodes with their whitespace collapsed", () => {
    const pieces = [
      t("Every  vertex of the "),
      t("median\n polytope is integral."),
    ];
    expect(findIn(pieces, "vertex of the median polytope")).toEqual({
      start: [0, 7],
      end: [1, 16],
    });
  });
  it("take a formula or a command whole, as a selection quotes it", () => {
    const pieces = [
      t("the order "),
      tex("$\\sigma$"),
      t(" minimises "),
      tex("\\cite{Bel19}"),
    ];
    expect(findIn(pieces, "order $\\sigma$ minimises \\cite{Bel19}")).toEqual({
      start: [0, 4],
      end: [3, 12],
    });
    expect(findIn(pieces, "$\\sigma$ minimises")).toEqual({
      start: [1, 0],
      end: [2, 10],
    });
  });
  it("are not found when they are not there, or are nothing", () => {
    expect(findIn([t("a b c")], "b d")).toBeNull();
    expect(findIn([t("a b c")], "   ")).toBeNull();
  });
});

/** A MathML element as `mathText` reads one: its name, and its children or, for a leaf, its text. */
const leaf = (name: string, text: string): MathNode => ({ localName: name, textContent: text, children: [], getAttribute: () => null });
const ml = (name: string, ...kids: (MathNode | string)[]): MathNode => {
  const children = kids.map((k) => (typeof k === "string" ? leaf("mi", k) : k));
  return { localName: name, textContent: children.map((c) => c.textContent ?? "").join(""), children, getAttribute: () => null };
};

describe("a formula as the reader sees it", () => {
  it("is its symbols, never its TeX", () => {
    expect(mathText(ml("math", "σ"))).toBe("σ");
  });
  it("reads scripts with ^ and _, a script of several symbols in brackets", () => {
    // \mathbb{Z}^{A(Q)}
    expect(mathText(ml("math", ml("msup", "ℤ", ml("mrow", "A", leaf("mo", "("), "Q", leaf("mo", ")")))))).toBe("ℤ^(A(Q))");
    expect(mathText(ml("math", ml("msubsup", "x", "i", leaf("mn", "2"))))).toBe("x_i^2");
  });
  it("spaces a relation and an operation, and keeps brackets and commas tight", () => {
    // \|w\| \le k, f(x)
    const f = ml("math", leaf("mo", "‖"), "w", leaf("mo", "‖"), leaf("mo", "≤"), "k", leaf("mo", ","), "f", leaf("mo", "⁡"), leaf("mo", "("), "x", leaf("mo", ")"));
    expect(mathText(f)).toBe("‖w‖ ≤ k, f(x)");
  });
  it("reads a fraction as a/b and a root with √", () => {
    expect(mathText(ml("math", ml("mfrac", leaf("mn", "1"), leaf("mn", "2"))))).toBe("1/2");
    expect(mathText(ml("math", ml("msqrt", "n")))).toBe("√(n)");
  });
});

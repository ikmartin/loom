// Quoted words found in a fragment's text as `quoteOf` reads a selection: whitespace collapsed, a formula or a command whole as its TeX.
import { describe, expect, it } from "vitest";
import { findIn, type Piece } from "./quote";

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

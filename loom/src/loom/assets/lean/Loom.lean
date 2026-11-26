/-
The marker loom reads when it checks this project. Kept by loom; an edit here is put back.

`@[loom "NAME"]` on a declaration says that it states the result loom knows by NAME: a label of the person's drafts, such as `thm:rank`, or a library node's id. A result may be stated by several declarations together; a declaration with no marker only supports one. Write the marker on an `axiom` to assume a library result rather than prove it.
-/
import Lean

open Lean

/-- `@[loom "NAME"]`: this declaration states the result loom knows by NAME. -/
syntax (name := loom) "loom " str : attr

initialize registerBuiltinAttribute {
  name := `loom
  descr := "the result of the quilt this declaration states"
  applicationTime := .afterTypeChecking
  add := fun decl stx _kind => do
    let `(attr| loom $s:str) := stx | throwError "write the marker as @[loom \"NAME\"]"
    let marker := decl ++ `_loom
    if (← getEnv).contains marker then
      throwError "{decl} already names a result"
    addDecl <| .defnDecl {
      name := marker, levelParams := [], type := mkConst ``String, value := mkStrLit s.getString,
      hints := .abbrev, safety := .safe }
}

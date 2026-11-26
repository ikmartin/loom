/-
Loom's probe of a built Lake project. Given the project's own build (`own=DIR`), each package's (`path=DIR`) and the project's module names, it finds modules in the toolchain first, refuses an import the project built that is not among those named, reads their .olean files as leanchecker does, imports only the modules they import from outside the project, with no initializer and no environment extension run, and hands every declaration of the project to Lean's kernel over them: nothing the project's modules hold executes here. Then it reads those same declarations. It prints one JSON object: `replay`, whether the kernel accepted every declaration (`exit` 0) or what it said; `modules`, each module's imports within the project; and `declarations`, each with its module, kind, statement, the axioms it rests on, the marker naming it, the declarations of the project it uses directly, and those its statement names (`means`). A declaration Lean made for another (`Name.isInternalDetail`) is listed with no axioms, so that what reaches through it is followed.
-/
import Lean

open Lean

/-- An expression written out with its binders' names left out, so a name Lean chose (an instance's, a hygienic one) or a renamed variable does not change it; how each binder is bound is kept. -/
partial def canon : Expr → String
  | .bvar i => s!"#{i}"
  | .fvar id => s!"(fvar {id.name})"
  | .mvar id => s!"(mvar {id.name})"
  | .sort u => s!"(Sort {u})"
  | .const n us => s!"{n}.\{{us}}"
  | .app f a => s!"({canon f} {canon a})"
  | .lam _ t b bi => s!"(fun {repr bi} {canon t} => {canon b})"
  | .forallE _ t b bi => s!"(forall {repr bi} {canon t}, {canon b})"
  | .letE _ t v b nd => s!"(let {nd} {canon t} := {canon v}; {canon b})"
  | .lit (.natVal n) => s!"{n}"
  | .lit (.strVal v) => s!"{repr v}"
  | .mdata _ e => canon e
  | .proj s i e => s!"({s}.{i} {canon e})"

/-- What a declaration says: its type, and its value where the value is part of its meaning. -/
def statement (find : Name → Option ConstantInfo) : ConstantInfo → String
  | .defnInfo v => s!"def {v.levelParams} : {canon v.type} := {canon v.value}"
  | .thmInfo v => s!"theorem {v.levelParams} : {canon v.type}"
  | .axiomInfo v => s!"axiom {v.levelParams} : {canon v.type}"
  | .opaqueInfo v => s!"opaque {v.levelParams} : {canon v.type}"
  | .quotInfo v => s!"quot {v.levelParams} : {canon v.type}"
  | .inductInfo v =>
    let ctors := v.ctors.map fun c => s!"| {c} : {(find c).map (canon ·.type) |>.getD "?"}"
    s!"inductive {v.levelParams} : {canon v.type} {v.numParams} {v.numIndices} {ctors}"
  | .ctorInfo v => s!"ctor : {canon v.type}"
  | .recInfo v => s!"rec : {canon v.type}"

/-- A declaration's kind as a record names it; loom reads no attribute, so a structure is any one-constructor type with no indices that is not recursive. -/
def kind : ConstantInfo → String
  | .defnInfo v => if v.hints matches .abbrev then "abbrev" else "def"
  | .thmInfo _ => "theorem"
  | .axiomInfo _ => "axiom"
  | .opaqueInfo _ => "opaque"
  | .inductInfo v => if v.ctors.length == 1 && v.numIndices == 0 && !v.isRec then "structure" else "inductive"
  | _ => "other"

/-- The constants a declaration mentions, in its type and in its value. -/
def mentions : ConstantInfo → Array Name
  | .defnInfo v => (v.type.getUsedConstants ++ v.value.getUsedConstants)
  | .thmInfo v => (v.type.getUsedConstants ++ v.value.getUsedConstants)
  | .opaqueInfo v => (v.type.getUsedConstants ++ v.value.getUsedConstants)
  | .inductInfo v => v.type.getUsedConstants
  | c => c.type.getUsedConstants

/-- The constants what a declaration says mentions: its type, and its value where `statement` takes the value in, and a type's constructors' types. -/
def meaning (find : Name → Option ConstantInfo) : ConstantInfo → Array Name
  | .defnInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .inductInfo v => v.ctors.foldl (fun acc c => acc ++ ((find c).map (·.type.getUsedConstants) |>.getD #[])) v.type.getUsedConstants
  | c => c.type.getUsedConstants

/-- The axioms a constant rests on, walking every body it reaches, each constant once over the whole run. -/
partial def axiomsOf (find : Name → Option ConstantInfo) (c : Name) : StateM (NameMap NameSet) NameSet := do
  if let some found := (← get).find? c then return found
  modify (·.insert c {})
  let walk (e : Expr) : StateM (NameMap NameSet) NameSet :=
    e.getUsedConstants.foldlM (fun acc d => return acc.append (← axiomsOf find d)) {}
  let found ← match find c with
    | some (.axiomInfo v) => return (← walk v.type).insert c
    | some (.defnInfo v) => return (← walk v.type).append (← walk v.value)
    | some (.thmInfo v) => return (← walk v.type).append (← walk v.value)
    | some (.opaqueInfo v) => return (← walk v.type).append (← walk v.value)
    | some (.inductInfo v) => v.ctors.foldlM (fun acc d => return acc.append (← axiomsOf find d)) (← walk v.type)
    | some info => walk info.type
    | none => pure {}
  modify (·.insert c found)
  return found

/-- A module's data, read from its .olean and the module system's parts beside it, as leanchecker reads them: its imports, and the constants of its most private part. -/
unsafe def readModule (m : Name) : IO (Array Import × Array ConstantInfo) := do
  let file ← findOLean m
  let mut fnames := #[file]
  let server := OLeanLevel.server.adjustFileName file
  if ← server.pathExists then
    fnames := fnames.push server
    let priv := OLeanLevel.private.adjustFileName file
    if ← priv.pathExists then
      fnames := fnames.push priv
  let parts ← readModuleDataParts fnames
  let some (first, _) := parts[0]? | throw <| IO.userError s!"could not read the module {m}"
  let some (last, _) := parts.back? | throw <| IO.userError s!"could not read the module {m}"
  return (first.imports, last.constants)

unsafe def main (args : List String) : IO UInt32 := do
  -- `own=DIR`, the project's own build; `path=DIR`, a package's build; the rest, the project's modules
  let own := args.filterMap (·.dropPrefix? "own=" |>.map (·.toString)) |>.head? |>.getD "/nowhere"
  let paths := args.filterMap (·.dropPrefix? "path=" |>.map (fun d => System.FilePath.mk d.toString))
  let mods := args.filter (fun a => !a.startsWith "own=" && !a.startsWith "path=") |>.map String.toName
  -- the toolchain's own modules first, so no build can stand in for Init or Lean
  initSearchPath (← findSysroot)
  searchPathRef.modify (· ++ paths ++ [System.FilePath.mk own])
  let ours : NameSet := mods.foldl (·.insert ·) {}
  let mut modules : Array (String × Json) := #[]
  let mut outside : Array Import := #[]
  let mut constants : Std.HashMap Name ConstantInfo := {}
  let mut held : Array (Name × Array ConstantInfo) := #[]
  for m in mods do
    let (imports, consts) ← readModule m
    modules := modules.push (m.toString, toJson (imports.filter (ours.contains ·.module) |>.map (·.module.toString)))
    outside := outside ++ imports.filter (!ours.contains ·.module)
    unless (← findOLean m).toString.startsWith (own ++ "/") do
      throw <| IO.userError s!"the module {m} is not the project's own build"
    for c in consts do
      constants := constants.insert c.name c
    held := held.push (m, consts)
  -- a module the project built that is not among those given would be imported unchecked
  for i in outside do
    if (← findOLean i.module).toString.startsWith (own ++ "/") then
      throw <| IO.userError s!"the module {i.module} is the project's own and not one loom checks"
  let env ← importModules outside {} (loadExts := false)
  let replay ← try
      discard <| env.toKernelEnv.replay constants
      pure (Json.mkObj [("exit", toJson (0 : Nat)), ("output", toJson "")])
    catch e =>
      pure (Json.mkObj [("exit", toJson (1 : Nat)), ("output", toJson e.toString)])
  let find (c : Name) : Option ConstantInfo := constants[c]? <|> env.find? c
  let owner (c : Name) : Name := match find c with
    | some (.ctorInfo v) => v.induct
    | some (.recInfo v) => v.getMajorInduct
    | _ => c
  let mut decls : Array Json := #[]
  let mut seen : NameMap NameSet := {}
  for (m, consts) in held do
    for c in consts do
      if c matches .ctorInfo _ || c matches .recInfo _ || c matches .quotInfo _ then continue
      let marker := match c with
        | .defnInfo v => if c.name matches .str _ "_loom" then
            match v.value with | .lit (.strVal s) => some s | _ => none
          else none
        | _ => none
      let internal := c.name.isInternalDetail
      let mut axioms := #[]
      unless internal do
        let (found, s) := (axiomsOf find c.name).run seen
        seen := s
        axioms := found.toArray.qsort Name.lt
      let uses := (mentions c).map owner |>.filter fun n => n != c.name && constants.contains n
      let means := (meaning find c).map owner |>.filter fun n => n != c.name && constants.contains n
      decls := decls.push <| Json.mkObj [
        ("name", toJson c.name.toString), ("module", toJson m.toString), ("kind", toJson (kind c)),
        ("internal", toJson internal), ("statement", toJson (statement find c)),
        ("means", toJson ((means.foldl (·.insert ·) ({} : NameSet)).toArray.map (·.toString))),
        ("axioms", toJson (axioms.map (·.toString))), ("marker", toJson marker),
        ("uses", toJson ((uses.foldl (·.insert ·) ({} : NameSet)).toArray.map (·.toString)))]
  IO.println (Json.mkObj [("replay", replay), ("modules", Json.mkObj modules.toList), ("declarations", Json.arr decls)]).compress
  return 0

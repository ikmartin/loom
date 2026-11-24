"""The library as one store of nodes (docs/design/library.md, docs/specs/nodes.md): a file each, the checks a file must pass, the index loom derives from the files, and the log of tags.

`ids` is the grammar of an id; `node` reads and writes one file. `carry` alone reads the library an earlier loom left (layout format 1), to bring a quilt forward.
"""

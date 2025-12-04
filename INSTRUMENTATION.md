# Firmament2 Instrumentation

Gates:
- `FIRMAMENT2_ENABLE=1`             # emit events
- `FIRMAMENT2_INCLUDE_CODE_META=1`  # include metadata in CODE_* events

Emitters:
- Tokenizer: Parser/lexer/lexer.c → `emit_tokenizer_event_json` via `_PyTokenizer_Get`
- AST: Parser/asdl_c.py → Python/Python-ast.c → `emit_ast_event_json`
- Source scope: Python/compile.c & Python/pythonrun.c → `_firm2_source_begin/_end` push/pop the current source filename+`source_id` (passed through to tokenizer/AST/codegen)
- Code lifecycle: Objects/codeobject.c → `_firm2_emit_code_create_meta/_destroy_meta` (+ `co_extra` provenance)
- Frame lifecycle: Python/ceval.c → `_firm2_emit_frame_event` on both frame enter and exit
- Common envelope everywhere: `event_id`, `pid`, `tid`, `ts_ns`

SOURCE_BEGIN/SOURCE_END appear exactly once per compile/execute entry point. They are wired in:
- `Python/compile.c`: `_PyAST_Compile` wraps AST-to-bytecode compilation, so the tokenizer, AST, and code lifecycle emitters can inherit `filename`/`source_id` even for in-memory sources.
- `Python/pythonrun.c`: `pyrun_file`, `_PyRun_StringFlagsWithName`, and `run_mod` bracket execution of file-backed and string-backed code, ensuring the active source scope is visible to downstream events.

## Build, install, and test on Linux

The emitters are part of the normal CPython binary. On a Debian/Ubuntu system, install prerequisites and build the tree at the repository root:

```bash
sudo apt update
sudo apt install build-essential gdb lcov pkg-config \
     libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev \
     liblzma-dev libncursesw5-dev libreadline6-dev libsqlite3-dev \
     libssl-dev tk-dev uuid-dev xz-utils zlib1g-dev

# Configure a local, prefix-isolated build so you do not overwrite system python
./configure --prefix="$(pwd)/build-env" --with-pydebug=no

# Compile and install the instrumented interpreter
make -j"$(nproc)"
make install

# Point helper shim (optional convenience)
ln -sf python3.14 build-env/bin/python
```

### Full emitter exercise (compile, install, and verify every event kind)

The following script compiles/installs the interpreter (if not already built), executes a short program that triggers every custom emitter, writes the NDJSON events to a file, and prints at least one example event of each type back to the terminal.

```bash
# Build + install (skipped if already done)
./configure --prefix="$(pwd)/build-env" --with-pydebug=no
make -j"$(nproc)"
make install
ln -sf python3.14 build-env/bin/python

# Run a program that exercises all emitters and capture output
cat > /tmp/firm2_demo.py <<'PY'
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

class Greeter:
    def greet(self):
        return "hi"

print(fib(4))
print(Greeter().greet())
PY

FIRMAMENT2_ENABLE=1 FIRMAMENT2_INCLUDE_CODE_META=1 \
  ./build-env/bin/python -I -S /tmp/firm2_demo.py > /tmp/firm2_events.ndjson

# Show a representative event for every emitter from the captured file
printf "\nSOURCE scope events (BEGIN/END):\n" && \
  grep -m1 '"SOURCE_BEGIN"' /tmp/firm2_events.ndjson && \
  grep -m1 '"SOURCE_END"' /tmp/firm2_events.ndjson

printf "\nTokenizer event:\n" && \
  grep -m1 '"type":"tokenizer"' /tmp/firm2_events.ndjson

printf "\nAST event:\n" && \
  grep -m1 '"type":"ast"' /tmp/firm2_events.ndjson

printf "\nCode lifecycle (CREATE/DESTROY):\n" && \
  grep -m1 '"CODE_CREATE"' /tmp/firm2_events.ndjson && \
  grep -m1 '"CODE_DESTROY"' /tmp/firm2_events.ndjson

printf "\nFrame lifecycle (ENTER/EXIT):\n" && \
  grep -m1 '"FRAME_ENTER"' /tmp/firm2_events.ndjson && \
  grep -m1 '"FRAME_EXIT"' /tmp/firm2_events.ndjson
```

Each line in `/tmp/firm2_events.ndjson` is NDJSON with the common envelope (`event_id`, `pid`, `tid`, `ts_ns`) and the emitter-specific payload fields, letting you inspect or post-process the full stream.

Some prose, then a Python block:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

An inline `snippet`, then a shell block:

```bash
echo "hi" && ls -la
```

A table for good measure:

| lang   | typed |
| ------ | ----- |
| python | yes   |
| bash   | no    |

And a block in an unknown language:

```nope
just text, no lexer here
```

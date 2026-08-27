# Local evaluation scaffold

This folder never contains customer documents or golden confidential values. Point the runner
to external sample folders and a local or deployed parser endpoint:

```powershell
$env:ORDER_PARSER_SAMPLE_DIRS = @(
  "C:\path\to\USA",
  "C:\path\to\USA Metals"
) -join [IO.Path]::PathSeparator
$env:ORDER_PARSER_ENDPOINT = "http://localhost:8088"
python evaluation\run_evaluation.py
```

The runner prints aggregate counts only: documents evaluated, response statuses, review counts,
and file extensions. It does not write document content or extracted values to disk.


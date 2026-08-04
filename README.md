<p align="center">
  <img src="assets/branding/github-banner.png" alt="PCCOOLER-LCD Control banner">
</p>

# PCCOOLER-LCD Control 3.0.0 Beta 13

Beta 13 is the **Protocol Lab** release.

## Show the protocol catalog

```fish
pccooler-lcd-control protocol-catalog
```

## Decode a packet

```fish
pccooler-lcd-control protocol-decode \
  --hex 5a005631203230300d0a...
```

## Record a request session

```fish
pccooler-lcd-control protocol-request "GET status" \
  --json '{}' \
  --execute \
  --session-trace /tmp/cp3-session.json
```

## View a trace

```fish
pccooler-lcd-control protocol-trace-show \
  /tmp/cp3-session.json \
  --summary
```

## Replay a recorded non-file request

Dry run:

```fish
pccooler-lcd-control protocol-replay \
  /tmp/cp3-session.json
```

Execute:

```fish
pccooler-lcd-control protocol-replay \
  /tmp/cp3-session.json \
  --execute
```

## Rate-limited probing

```fish
pccooler-lcd-control protocol-probe \
  docs/protocol/candidate-read-methods.txt
```

Nothing is sent without `--execute`.

```fish
pccooler-lcd-control protocol-probe \
  docs/protocol/candidate-read-methods.txt \
  --execute \
  --interval 1.0 \
  --stop-after 5 \
  --trace /tmp/cp3-probe.json
```

Only read-style candidate methods are included. Electron IPC names are not
assumed to be CP3 wire-protocol methods.

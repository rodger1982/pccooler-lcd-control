# PCCOOLER-LCD Control 3.0.0 Beta 12

Beta 12 fixes the experimental native-media upload class methods.

```fish
systemctl --user stop pccooler-lcd-control.service

pccooler-lcd-control media-upload \
  ~/Pictures/pccooler-images/4-3.mp4 \
  --remote-name test.mp4 \
  --execute \
  --verbose
```

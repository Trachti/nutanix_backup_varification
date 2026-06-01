# Nutanix Backup Verification

Verify recent Nutanix recovery points and Prism Element snapshots for a VM.

## Features

- Python standard library only
- JSON output support
- Safe, audit-oriented behavior
- Placeholder configuration for Nutanix environments

## Configuration

Edit `nutanix_backup_verification.py` and configure the placeholder values. Do not commit real API tokens, passwords, UUIDs, IP addresses, or internal infrastructure details to a public repository.

## Usage

```bash
python nutanix_backup_verification.py --vm server01 --mode both --max-age-hours 24
```

## Security Notes

The script currently disables SSL certificate verification by using `ssl._create_unverified_context()`. This may be useful in lab environments, but it is not recommended for production. For production use, configure proper certificate validation.

## Disclaimer

This script is provided as an example. Test it in a safe environment before using it against production Nutanix infrastructure.

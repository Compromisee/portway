# Security

Portway is a local port discovery tool. It is meant to chart services on machines and networks you already use.

## Scope

Please report vulnerabilities that would let Portway:

- scan or request hosts outside loopback, the attached RFC1918 / Tailscale / link-local ranges
- execute unexpected commands from crafted interface names, hostnames, or Tailscale JSON
- exfiltrate scan results
- open non-http(s) URLs from the Open action

## Out of scope

- Finding open ports on a network the operator is attached to (that is the product)
- Services you expose yourself with weak authentication

## Reporting

Open a private security advisory on the GitHub repository, or email the maintainer listed on the repo. Please do not file a public issue for an exploitable bug until a fix is available.

We aim to acknowledge reports within one week.

<table align="center">
<tr><td align="center" width="640">

## ▶&nbsp; [Open the interactive map](https://oyatrino.github.io/tezosprotocolmap/)

🌍 &nbsp;Every Tezos protocol upgrade mapped to its namesake city, with on-chain governance history

</td></tr>
</table>

# tezos protocols map

[![Built with Periplum](https://img.shields.io/badge/built_with-Periplum-4da3ff)](https://periplum.js.org)
Mapping Tezos protocol names on the globe

[![Update GPX](https://github.com/oyatrino/tezosprotocolmap/actions/workflows/update-gpx.yml/badge.svg)](https://github.com/oyatrino/tezosprotocolmap/actions/workflows/update-gpx.yml)
[![protocols](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/oyatrino/tezosprotocolmap/main/protocol-count.json)](protocols.json)

![Tezos Protocol Cities Map](map.png)

## context
* *cheeses* for feature test nets 
    * => no clear list for those AFAIK.

* *cities* for protocols testnets and protocols applied on mainnet 
    * => cf. https://octez.tezos.com/docs/protocols/naming.html
    * can be mapped :-) 

## data sources
`protocols.json` is built by [`scripts/update_gpx.py`](scripts/update_gpx.py) from:

* **Protocol naming (mainnet & testnet cities)** — the octez docs naming page:
  https://octez.tezos.com/docs/protocols/naming.html
* **Testnet-only protocols** — teztnets.com:
  https://teztnets.com/teztnets.json
* **Activation dates, protocol hashes & on-chain voting results** — the TzKT API:
  https://api.tzkt.io

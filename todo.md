### Demand modelling

- [x] plug in CCC CB7 2050 demand scenarios
- [x] make it easy to switch between different demand models
- [x] do better than averaging the gas demand (repeat it)
- [x] use ERA5 heating degree days for an independent way to model seasonality
- [ ] more accurate estimate for the space heating demand


### Supply modelling

- [x] check wind/solar mix from CB7 and FES (or try optimising ourselves)
- [x] granular supply model using renewables ninja
- [x] integrate new ERA5 datasets


### Energy system modelling

- [x] implement storage model
- [x] add losses from transmission and distribution
    - FES 2025 states that transmission losses are around 2% today but increasing to 3% by 2050
    - Distribution losses are higher, typically around 5-8%
    - DUKES 2024 says that 2023 total losses are around 9%
    - If we look at the ratio of demand from the CCC hourly data which accounts for losses and compare with the end use demand, we get around 11.3% total losses
- [x] add interconnectors
    - Maj looked at this already, found approx 14 GW capacity meeting on average 6% of demand per year
    - Can probably get these numbers from ESPENI dataset, and other sources
    - CB7 says 28 GW capacity by 2050, FES 2025 has 21.8 GW
    - Current imports today are around 20 TWh
- [x] add dispatchable low carbon generation (gas + CCS)
    - Review CB7, FES 2025, and RS report assumptions
    - In CB7 it's about 18 GW (20 GW is cited for electrolyser and total low carbon dispatchable generation is 38 GW). They also emphasise that the exact tradeoff between gas and hydrogen generation is uncertain, and will depend on the evolution of costs and efficiencies.
- [x] Medium term storage (CB7): A range of other options can provide storage over the medium term (days-to-weeks), including pumped hydro and other technologies at different stages of commercialisation (for example, compressed and liquid air storage, flow batteries, and thermal storage). Our analysis deploys 7 GW of medium-duration grid storage by 2050, (433 GWh of storage capacity).
- [x] use numba to speed up the core simulation loop
- [x] add a limit to hydrogen burning power
- [ ] configurable simulation start storage levels (test 0, 50%, 100% full)
- [ ] add the option to run dac / gas+ccs as base load (rather than only when there is a surplus)
- [ ] move to hourly time resolution
- [ ] allow some power outages
    - very small discrepancies can be managed tolerated?
    - allow rare outages, e.g. per decade level
    - factor in lost load costs to the energy cost model

### Economic modelling

- [ ] add costs
    - [x] everything else
    - [ ] interconnects
- [ ] improve cost assummptions
- [ ] automatically find cost optimised solutions

### Net zero modelling

- [ ] add emissions reporting for different power sources
- [ ] add Enhanced Rock Weathering for removals
- [ ] add BECCS

### Analysis & visualisation

- [x] Look at total unmet demand instead of fraction days with unmet demand
- [ ] Also plot unmet demand as a function of day of year
- [ ] Improve visualisation of single simulation result
- [ ] Do those 40 year plots but X axis is a single year, to see if there are yearly trends 
- [ ] Add more of Rei's DAC plots (energy cost, £ cost, net negative emissions scenarios, etc)

### Paper ideas

- reproduce and expand on the RS study
- with a more sophisticated and realistic energy system model that is more aligned with CCC and FES assumptions
- use a dataset(s) that is more recent and longer term 

look at related papers
- https://www.sciencedirect.com/science/article/pii/S2666792424000234
- https://www.nature.com/articles/s41597-024-04129-8

datasets
- https://zenodo.org/records/13938926
- https://researchdata.reading.ac.uk/321/
- https://researchdata.reading.ac.uk/239/
- https://tyndp.entsoe.eu/resources/demand-time-series-2040-national-trends

other projects
- https://www.ucl.ac.uk/bartlett/environment-energy-resources/energy/research-ucl-energy-institute/energy-systems-and-artificial-intelligence-lab
- https://news.ycombinator.com/item?id=45114277
- https://github.com/andrewlyden/PyPSA-GB

# Research-reporting acceptance examples

| Request/context | Expected behavior | Unacceptable behavior |
|---|---|---|
| Report requested without current graph | Prepare only eligible graph prerequisites or explain blocker | Announce a verified report |
| Current explanation accepted; explicit resume offers report option | Select the supplied report option | Repeat old explanation or use old aliases |
| Report tool succeeded but verifier says release_blocked | Explain the verifier's restriction | Treat execution success as verified/exportable |
| User asks for a private report | Use private delivery controls | Publish, share or automatically generate public export |

The live case `report-boundary` checks routing and gap handling. Existing assessment
handoff fixtures verify graph/explanation/report ordering and exact scope consent.

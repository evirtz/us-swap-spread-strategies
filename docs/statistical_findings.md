# Statistical findings

The trading rule can earn positive returns even when the evidence for a stable long-run relationship is weak. It trades deviations from a rolling reference, and its total return also includes modeled carry and rolldown. The statistical tests ask narrower questions about integration, cointegration, coefficient stability and spread adjustment.

These tests cover the SOFR 10-year spread against GBP/EUR 2-year and 5-year basis, with or without MOVE. They do not establish the same findings for the 30-year strategies.

## Cointegration

Spread and basis levels generally behave as nonstationary series, while their changes look stationary. MOVE is less clear: the integration tests do not give a consistent classification. This matters when interpreting systems that include it.

Full-sample cointegration evidence depends on lag selection, deterministic terms, the test used and whether MOVE is included. Under the primary Engle–Granger AIC specification, no spread/basis pair passes at 5% without MOVE. With MOVE, GBP2Y, GBP5Y and EUR2Y pass the four-model Holm correction, while EUR5Y does not. None of the twelve final rolling training windows passes that primary Engle–Granger test.

Johansen trace and maximum-eigenvalue tests also give specification-dependent ranks. If MOVE is stationary, a positive rank in a three-variable system can reflect MOVE itself rather than a stable spread/basis relationship. Break tests and conditional bounds sensitivities do not remove that uncertainty.

## Spread adjustment

All twelve rolling-gap adjustment coefficients have the expected negative sign: a spread above its reference is associated with a subsequent fall, holding the modeled short-run changes constant. None passes the primary Holm correction across twelve comparisons.

When the tests are grouped separately by currency, GBP5Y R1 passes the six-model correction at 5% in the primary one-close test, with adjusted p = 0.0445. That currency grouping was examined after the original twelve-model comparison. It controls each currency separately and does not correct the wider strategy search.

The response is measured from the signal close to the next recorded close. The strategy enters at that next close, so this finding does not directly test the return earned after entry. The gap is also an estimated regressor, making the reported adjustment p-values descriptive rather than definitive validation of the trading rule.

## Coefficients and inference

Basis coefficients change across windows and dates. A changing rolling estimate can reflect sampling noise, changing economic conditions or model misspecification. It is not, by itself, proof that cointegration is impossible. It does weaken the claim that one stable hedge ratio explains the whole sample.

HAC standard errors account for heteroskedasticity and serial correlation in the stated regression inference. They do not make nonstationary levels regressions reliable or establish cointegration. The endpoint regression tables use an approximate Student-t reference; the rolling adjustment regressions use a normal reference. Their statistics should not be described interchangeably as ordinary t-tests.

The saved tables and [research runner](../research/README.md) retain the specifications and probability conventions used in the study. Johansen is reported against critical values, not fabricated exact p-values.

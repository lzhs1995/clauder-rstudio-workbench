# APIM Path Mapping

Preserve the actual model's member dictionary, variable coding and constraints.
Do not infer actor/partner roles from suffixes such as AAM1 or PAM2 alone.

For members m/f, a direct APIM can be written as:

- Ym <- a_m Xm + p_m Xf + covariates
- Yf <- a_f Xf + p_f Xm + covariates

Correlated member outcomes and predictors reflect the dyadic specification; equality
constraints are explicit model choices. A filename containing saturated is not a
proof of zero degrees of freedom or fit quality.

For APIMeM, trace each mediated path as X(source) -> M(member) -> Y(target).
Classify each arrow as actor (same member) or partner (different member). For
example Xm -> Mm -> Ym is AA, Xm -> Mm -> Yf is AP, Xm -> Mf -> Yf is PA, and
Xm -> Mf -> Ym is PP. The reverse-source paths follow the same rule. Store these
three variables, both path labels and the final product in a path dictionary.

Moderation requires explicit interaction construction and moderator coding.
For b(W) = b0 + b1 W, the conditional mediated effect is a * b(W) when only b is
moderated. If both a and b are moderated, expand their product; the derivative is
not generally a single constant index. Read the actual MODEL CONSTRAINT formula
before naming a parameter an index of moderated mediation.

Continuous moderator values, binary effect codes and reference groups must match
the template and postprocessing. Preserve intended 90/95/99 percent interval
levels. Keep bootstrap CI decisions distinct from normal-theory Wald p-values.

GH5 bootstrap parameters must be aligned to their statements/labels and point
estimates. Verify matrix orientation and actual draw counts. An old R function
selecting V3:V1002 or a shorter range can silently use fewer than the requested
1,000 draws. Historical reproduction records that behavior; changing it belongs
in a separate corrected analysis with a numeric comparison.

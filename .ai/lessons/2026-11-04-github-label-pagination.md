# Paginate GitHub label existence checks

The step-1 PR label guard queried only GitHub's default first page, silently
skipping existing review and risk-high labels. Check the complete taxonomy with
`gh api --paginate .../labels` and read back the applied PR labels. A guarded skip
is not proof a label is absent. Both required labels were restored before review.

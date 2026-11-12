# Wdrożenie dema w AWS i Azure

Instrukcja dla właściciela. Wybór usług i źródła są w
[specyfikacji](../.ai/specs/2026-11-12-cloud-deployment.md). Ceny i dokumentację
sprawdzono 2026-11-12.

Jeden obraz kontenera (`ghcr.io/wojski999/propane-reconciliation-demo`) działa w
obu chmurach. Serwuje raport `showcase` wygenerowany z danych przykładowych z repo,
bez sekretów i bez połączeń z innymi systemami.

| Chmura | Usługa | Adres HTTPS |
|---|---|---|
| AWS | Lightsail Containers, Nano | `*.cs.amazonlightsail.com` |
| Azure | Container Apps, Consumption | `*.azurecontainerapps.io` |

## Koszt miesięczny

| Usługa | Cena | Darmowy limit? | Źródło |
|---|---|---|---|
| Lightsail Nano | 7 USD/mies. | Nie | [cennik](https://aws.amazon.com/lightsail/pricing/) |
| Transfer Lightsail | 500 GB w cenie | Tak | [cennik](https://aws.amazon.com/lightsail/pricing/) |
| CloudFormation | 0 USD | Tak | [cennik](https://aws.amazon.com/cloudformation/pricing/) |
| AWS Budgets | 0 USD | Tak | [cennik](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/) |
| Container Apps | 0 USD | Tak | [cennik](https://azure.microsoft.com/en-us/pricing/details/container-apps/) |
| Budżet Azure | 0 USD | Tak | [dokumentacja](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets) |
| GHCR (publiczny) | 0 USD | Tak | [dokumentacja](https://docs.github.com/en/billing/concepts/product-billing/github-packages) |

Data sprawdzenia wszystkich wierszy: 2026-11-12.

- **AWS: ok. 7 USD/mies., poza darmowym limitem.** Lightsail Containers nie mają
  stałej darmowej puli. Nowe konto dostaje do 200 USD kredytów Free Tier na
  6 miesięcy ([FAQ](https://aws.amazon.com/free/free-tier-faqs/)), więc przez ten
  czas koszt pokrywają kredyty. Opłata naliczana jest za cały czas istnienia
  usługi, także bez ruchu. Po pokazaniu dema usuń je (polecenie niżej).
- **Azure: 0 USD w darmowej puli.** Co miesiąc darmowe są 180 000 vCPU-s,
  360 000 GiB-s i 2 mln żądań; aplikacja skaluje się do zera i wtedy nic nie
  kosztuje ([billing](https://learn.microsoft.com/en-us/azure/container-apps/billing)).
  Przy 0,25 vCPU i 0,5 GiB pula wystarcza na ok. 200 godzin aktywnej pracy w
  miesiącu. Pierwsze wejście po przerwie trwa kilka sekund dłużej (zimny start).
- Bez baz danych, CDN, rejestrów w chmurze i monitoringu: nic więcej nie nalicza
  opłat.

## Krok 0: GitHub (raz)

1. Po scaleniu tego PR workflow `Container` opublikuje obraz w GHCR.
2. Upublicznij paczkę (GHCR nie dziedziczy widoczności repo): GitHub → Twój
   profil → Packages → `propane-reconciliation-demo` → Package settings →
   Change visibility → Public.
3. Utwórz środowisko wdrożeniowe (w terminalu z `gh`):

   ```sh
   gh api -X PUT repos/wojski999/propane-reconciliation-demo/environments/cloud-deploy
   ```

Polecenia poniżej uruchamiasz w przeglądarkowej konsoli chmury (AWS CloudShell,
Azure Cloud Shell): CLI jest tam zainstalowane i zalogowane. Najpierw pobierz repo:

```sh
git clone https://github.com/wojski999/propane-reconciliation-demo.git
cd propane-reconciliation-demo
```

## AWS

1. **Konto**: <https://aws.amazon.com/free/> → Create an AWS account. Jeśli plan
   Free nie pozwoli utworzyć usługi Lightsail Containers, przejdź na plan Paid;
   pozostałe kredyty nadal działają.
2. **Budżet 5 USD**: konsola → Billing and Cost Management → Budgets → Create
   budget → Use a template → Monthly cost budget → Budgeted amount `5` → swój
   e-mail → Create budget.
3. **Rola dla GitHub Actions (OIDC, bez kluczy)**, w AWS CloudShell w katalogu repo:

   ```sh
   aws iam create-open-id-connect-provider \
     --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   sed "s/ACCOUNT_ID/$ACCOUNT_ID/" deploy/aws/github-trust-policy.json > /tmp/trust.json
   aws iam create-role --role-name propane-demo-deployer \
     --assume-role-policy-document file:///tmp/trust.json
   aws iam put-role-policy --role-name propane-demo-deployer \
     --policy-name propane-demo-deployer --policy-document file://deploy/aws/deployer-policy.json
   aws iam get-role --role-name propane-demo-deployer --query Role.Arn --output text
   ```

4. Skopiuj wypisany ARN i zapisz go jako sekret (lokalnie, `gh` zapyta o wartość):

   ```sh
   gh secret set AWS_DEPLOY_ROLE_ARN --env cloud-deploy --repo wojski999/propane-reconciliation-demo
   ```

**Dokładne uprawnienia roli** (`deploy/aws/deployer-policy.json`):

- tylko stos `propane-reconciliation-demo`:
  `cloudformation:CreateChangeSet`, `DeleteChangeSet`, `DeleteStack`,
  `DescribeChangeSet`, `DescribeStackEvents`, `DescribeStacks`,
  `ExecuteChangeSet`, `GetTemplateSummary`;
- Lightsail (lista z oficjalnego handlera `AWS::Lightsail::Container`):
  `lightsail:CreateContainerService`, `CreateContainerServiceDeployment`,
  `DeleteContainerService`, `GetContainerServices`, `TagResource`,
  `UntagResource`, `UpdateContainerService`.

Rolę może przejąć wyłącznie workflow z tego repo w środowisku `cloud-deploy`
(warunek `sub` w `deploy/aws/github-trust-policy.json`).

## Azure

1. **Konto**: <https://azure.microsoft.com/free/> → Start free.
2. **Budżet 5 USD**: portal → Cost Management → Budgets → Add → zakres:
   subskrypcja → Reset period Monthly → Amount `5` → alerty 80% i 100%
   (Actual) → swój e-mail → Create.
3. **Grupa zasobów, rola i tożsamość dla GitHub Actions (OIDC, bez sekretu
   klienta)**, w Azure Cloud Shell (Bash) w katalogu repo:

   ```sh
   SUB=$(az account show --query id -o tsv)
   az provider register --namespace Microsoft.App --wait
   az group create --name propane-reconciliation-demo --location westeurope
   sed "s/SUBSCRIPTION_ID/$SUB/" deploy/azure/deployer-role.json > /tmp/role.json
   az role definition create --role-definition @/tmp/role.json
   APP_ID=$(az ad app create --display-name propane-demo-deployer --query appId -o tsv)
   az ad sp create --id "$APP_ID"
   az ad app federated-credential create --id "$APP_ID" \
     --parameters deploy/azure/github-federated-credential.json
   az role assignment create --assignee "$APP_ID" --role "Propane Demo Deployer" \
     --scope "/subscriptions/$SUB/resourceGroups/propane-reconciliation-demo"
   echo "AZURE_CLIENT_ID=$APP_ID"
   echo "AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
   echo "AZURE_SUBSCRIPTION_ID=$SUB"
   ```

   Rola może się pojawić z opóźnieniem do kilku minut; gdy przypisanie zgłosi
   brak roli, powtórz ostatnie `az role assignment create`.

4. Zapisz trzy wypisane wartości jako sekrety (lokalnie, `gh` zapyta o każdą):

   ```sh
   for s in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do
     gh secret set "$s" --env cloud-deploy --repo wojski999/propane-reconciliation-demo
   done
   ```

**Dokładne uprawnienia roli „Propane Demo Deployer”** (`deploy/azure/deployer-role.json`),
przypisanej tylko do grupy `propane-reconciliation-demo`:

- `Microsoft.Resources/subscriptions/resourceGroups/read`
- `Microsoft.Resources/deployments/read`, `write`, `delete`, `validate/action`,
  `operations/read`, `operationstatuses/read`
- `Microsoft.App/managedEnvironments/read`, `write`, `delete`, `join/action`
- `Microsoft.App/containerApps/read`, `write`, `delete`
- `Microsoft.App/locations/*/read` (stan operacji asynchronicznych)

Wbudowana rola „Container Apps Contributor” nie wystarcza, bo nie tworzy
środowiska (`managedEnvironments/write`).

## Wdrożenie: jedno polecenie

```sh
gh workflow run deploy.yml --repo wojski999/propane-reconciliation-demo -f cloud=aws -f action=deploy
gh workflow run deploy.yml --repo wojski999/propane-reconciliation-demo -f cloud=azure -f action=deploy
```

Workflow loguje się przez OIDC, wdraża obraz z bieżącego commita `main`, czeka na
`/healthz` i wypisuje publiczny adres HTTPS w podsumowaniu biegu
(`gh run view --repo wojski999/propane-reconciliation-demo`). Bez sekretów kończy
się błędem przed jakimkolwiek krokiem w chmurze. Publiczny log biegu w zakładce
Actions jest sprawdzalnym dowodem wdrożenia.

Alternatywa z zalogowanym CLI (np. w CloudShell): `make deploy-aws` albo
`make deploy-azure`.

## Usunięcie wszystkiego: jedno polecenie

```sh
gh workflow run deploy.yml --repo wojski999/propane-reconciliation-demo -f cloud=aws -f action=destroy
gh workflow run deploy.yml --repo wojski999/propane-reconciliation-demo -f cloud=azure -f action=destroy
```

Alternatywa z CLI: `make destroy-aws` albo `make destroy-azure`. Usuwa wszystkie
zasoby, które kosztują. Rola, tożsamość, budżet i pusta grupa zasobów nie
kosztują nic i zostają na kolejne wdrożenie.

## Do sprawdzenia po dostarczeniu dostępów

Bez kont nie dało się tego udowodnić. Po wdrożeniu (`URL` z podsumowania biegu):

1. Publiczny adres HTTPS i zdrowie:
   `curl -i "$URL/"` (HTTP 200, `text/html`) oraz `curl -i "$URL/healthz"` (`ok`).
2. Certyfikat: `curl -vI "$URL/" 2>&1 | grep -E "subject:|issuer:|expire"`.
3. Czy uprawnienia wystarczają: zielony bieg `deploy` i `destroy` w Actions.
   Gdy brakuje uprawnienia, błąd `AccessDenied`/`AuthorizationFailed` podaje
   nazwę akcji: dopisz tylko ją do pliku polityki lub roli w osobnym PR.
4. Że usunięcie zadziałało:
   `aws lightsail get-container-services --region eu-central-1` (brak usługi) i
   `az resource list -g propane-reconciliation-demo -o table` (pusto).
5. Rachunek: po 24 h Billing (AWS) i Cost analysis (Azure) pokazują zgodny koszt;
   alert budżetowy ma adres e-mail.
6. Czy plan Free AWS pozwala na Lightsail Containers (krok AWS 1).

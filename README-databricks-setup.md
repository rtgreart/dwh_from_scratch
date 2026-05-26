# Setup Databricks su AWS — RetailCo

Manuale di configurazione completo per il workspace Databricks su AWS
con cluster general-purpose e Spot instances.

---

## Prerequisiti

- Account AWS attivo con carta di credito (piano paid, non free tier)
- Account Databricks — registrazione su [databricks.com/try-databricks](https://www.databricks.com/try-databricks)
- $400 di crediti Databricks trial (14 giorni)

> **Attenzione**: il piano AWS Free Tier non permette l'accesso al Marketplace.
> È necessario upgraidare ad un piano paid prima di procedere.

---

## Architettura

```
AWS Account
├── IAM Role: databricks-cross-account   # Permessi EC2 per i cluster
├── IAM Role: databricks-storage-role    # Accesso S3 per Unity Catalog
└── S3 Bucket: databricks-retailco-storage  # Storage workspace
```

---

## Step 1 — IAM Role per il Compute (Cross-Account)

Questo role permette a Databricks di creare e gestire istanze EC2
nel tuo account AWS.

### 1.1 Crea il role

1. Vai su **AWS Console → IAM → Roles → Create role**
2. Seleziona **AWS account → Another AWS account**
3. In **Account ID** inserisci: `414351767826` *(account ID fisso di Databricks)*
4. Spunta **Require external ID**
5. In **External ID** inserisci il tuo **Databricks Account ID**
   *(visibile nel form Databricks — campo External ID)*
6. Clicca **Next → Next**
7. **Role name**: `databricks-cross-account`
8. Clicca **Create role**

### 1.2 Aggiungi la policy inline

Apri il role → **Add permissions → Create inline policy → JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Stmt1403287045000",
      "Effect": "Allow",
      "Action": [
        "ec2:AllocateAddress",
        "ec2:AssignPrivateIpAddresses",
        "ec2:AssociateDhcpOptions",
        "ec2:AssociateIamInstanceProfile",
        "ec2:AssociateRouteTable",
        "ec2:AttachInternetGateway",
        "ec2:AttachVolume",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:CancelSpotInstanceRequests",
        "ec2:CreateDhcpOptions",
        "ec2:CreateFleet",
        "ec2:CreateInternetGateway",
        "ec2:CreateLaunchTemplate",
        "ec2:CreateLaunchTemplateVersion",
        "ec2:CreateNatGateway",
        "ec2:CreateRoute",
        "ec2:CreateRouteTable",
        "ec2:CreateSecurityGroup",
        "ec2:CreateSubnet",
        "ec2:CreateTags",
        "ec2:CreateVolume",
        "ec2:CreateVpc",
        "ec2:CreateVpcEndpoint",
        "ec2:DeleteDhcpOptions",
        "ec2:DeleteFleets",
        "ec2:DeleteInternetGateway",
        "ec2:DeleteLaunchTemplate",
        "ec2:DeleteLaunchTemplateVersions",
        "ec2:DeleteNatGateway",
        "ec2:DeleteRoute",
        "ec2:DeleteRouteTable",
        "ec2:DeleteSecurityGroup",
        "ec2:DeleteSubnet",
        "ec2:DeleteTags",
        "ec2:DeleteVolume",
        "ec2:DeleteVpc",
        "ec2:DeleteVpcEndpoints",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeFleetHistory",
        "ec2:DescribeFleetInstances",
        "ec2:DescribeFleets",
        "ec2:DescribeIamInstanceProfileAssociations",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeInstances",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeLaunchTemplates",
        "ec2:DescribeLaunchTemplateVersions",
        "ec2:DescribeNatGateways",
        "ec2:DescribePrefixLists",
        "ec2:DescribeReservedInstancesOfferings",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSpotInstanceRequests",
        "ec2:DescribeSpotPriceHistory",
        "ec2:DescribeSubnets",
        "ec2:DescribeVolumes",
        "ec2:DescribeVpcs",
        "ec2:DetachInternetGateway",
        "ec2:DisassociateIamInstanceProfile",
        "ec2:DisassociateRouteTable",
        "ec2:GetLaunchTemplateData",
        "ec2:GetSpotPlacementScores",
        "ec2:ModifyFleet",
        "ec2:ModifyLaunchTemplate",
        "ec2:ModifyVpcAttribute",
        "ec2:ReleaseAddress",
        "ec2:ReplaceIamInstanceProfileAssociation",
        "ec2:RequestSpotInstances",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RunInstances",
        "ec2:TerminateInstances"
      ],
      "Resource": ["*"]
    },
    {
      "Effect": "Allow",
      "Action": ["iam:CreateServiceLinkedRole", "iam:PutRolePolicy"],
      "Resource": "arn:aws:iam::*:role/aws-service-role/spot.amazonaws.com/AWSServiceRoleForEC2Spot",
      "Condition": {
        "StringLike": {
          "iam:AWSServiceName": "spot.amazonaws.com"
        }
      }
    }
  ]
}
```

**Policy name**: `databricks-ec2-policy` → **Create policy**

---

## Step 2 — S3 Bucket per lo Storage

### 2.1 Crea il bucket

1. **AWS Console → S3 → Create bucket**
2. **Nome**: `databricks-retailco-storage`
3. **Regione**: `eu-west-1` *(deve coincidere con la regione del workspace)*
4. **ACL**: disabilitate
5. **Blocca tutti gli accessi pubblici**: attivo
6. Clicca **Create bucket**

### 2.2 Aggiungi la bucket policy

**S3 → databricks-retailco-storage → Autorizzazioni → Bucket policy → Modifica**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Grant Databricks Access",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::414351767826:root"
      },
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::databricks-retailco-storage/*",
        "arn:aws:s3:::databricks-retailco-storage"
      ],
      "Condition": {
        "StringEquals": {
          "aws:PrincipalTag/DatabricksAccountId": ["<DATABRICKS-ACCOUNT-ID>"]
        }
      }
    },
    {
      "Sid": "Prevent DBFS from accessing Unity Catalog metastore",
      "Effect": "Deny",
      "Principal": {
        "AWS": "arn:aws:iam::414351767826:root"
      },
      "Action": ["s3:*"],
      "Resource": [
        "arn:aws:s3:::databricks-retailco-storage/unity-catalog/*"
      ]
    }
  ]
}
```

> Sostituisci `<DATABRICKS-ACCOUNT-ID>` con il tuo Databricks Account ID.

---

## Step 3 — IAM Role per lo Storage (Unity Catalog)

### 3.1 Crea il role con custom trust policy

1. **AWS Console → IAM → Roles → Create role**
2. Seleziona **Policy di attendibilità personalizzata**
3. Incolla questo JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": ["arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"]
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "0000"
        }
      }
    }
  ]
}
```

4. **Role name**: `databricks-storage-role` → **Create role**

### 3.2 Aggiorna la trust policy (self-assuming)

**IAM → databricks-storage-role → Relazioni di attendibilità → Modifica**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL",
          "arn:aws:iam::<AWS-ACCOUNT-ID>:role/databricks-storage-role"
        ]
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<DATABRICKS-ACCOUNT-ID>"
        }
      }
    }
  ]
}
```

### 3.3 Aggiungi la policy inline

**databricks-storage-role → Add permissions → Create inline policy → JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::databricks-retailco-storage/unity-catalog/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::databricks-retailco-storage"
    },
    {
      "Action": ["sts:AssumeRole"],
      "Resource": ["arn:aws:iam::<AWS-ACCOUNT-ID>:role/databricks-storage-role"],
      "Effect": "Allow"
    }
  ]
}
```

**Policy name**: `databricks-storage-policy` → **Create policy**

---

## Step 4 — Workspace Databricks

### 4.1 Crea il workspace

1. Vai su [accounts.cloud.databricks.com](https://accounts.cloud.databricks.com)
2. **Workspaces → Create workspace**
3. Seleziona **"Use your existing cloud account"**
4. Compila:
   - **Workspace name**: `retailco`
   - **Region**: `eu-west-1`
5. In **Compute credentials**: seleziona `databricks-cross-account`
6. In **Workspace storage**: seleziona **Add new cloud storage → Set up Manually**
   - **Storage configuration name**: `databricks-retailco-storage`
   - **Bucket name**: `databricks-retailco-storage`
   - **IAM role ARN**: `arn:aws:iam::<AWS-ACCOUNT-ID>:role/databricks-storage-role`
7. Clicca **Create workspace**

> **Importante**: NON usare "Use serverless compute with default storage" —
> quel workspace non supporta cluster general-purpose.

Attendi 5-10 minuti che lo stato diventi **Running**.

---

## Step 5 — Cluster General-Purpose

1. **Open workspace → Compute → Create compute**
2. Impostazioni:
   - **Compute name**: `retailco-cluster`
   - **Runtime**: 17.3 LTS (Spark 4.0)
   - **Node type**: `i3.xlarge` (30.5 GB, 4 Core)
   - **Single node**: ✓
   - **Terminate after**: `20` minuti
3. Clicca **Create**

---

## Riepilogo risorse create

| Risorsa | Nome | Tipo |
|---------|------|------|
| IAM Role compute | `databricks-cross-account` | Cross-account EC2 |
| IAM Policy compute | `databricks-ec2-policy` | Inline policy |
| S3 Bucket | `databricks-retailco-storage` | eu-west-1 |
| IAM Role storage | `databricks-storage-role` | Unity Catalog |
| IAM Policy storage | `databricks-storage-policy` | Inline policy |
| Workspace | `retailco` | eu-west-1, Premium |
| Cluster | `retailco-cluster` | i3.xlarge, Single node |

---

## Costi stimati

| Risorsa | Costo stimato |
|---------|---------------|
| i3.xlarge Spot | ~$0.10/ora |
| Databricks DBU | ~$0.15/ora |
| S3 storage | ~$0.023/GB/mese |
| **Totale cluster attivo** | **~$0.25/ora** |

Con $400 di crediti trial → ~100 ore di cluster attivo.

> Il cluster si spegne automaticamente dopo 20 minuti di inattività.

---

## Note importanti

- Il trial Databricks dura **14 giorni** — pianifica il lavoro di conseguenza
- Dopo la scadenza del trial il workspace passa a pay-as-you-go
- Cancella il workspace prima della scadenza se non vuoi addebiti
- Il workspace `retailco` con EC2 è separato dal workspace Free Edition

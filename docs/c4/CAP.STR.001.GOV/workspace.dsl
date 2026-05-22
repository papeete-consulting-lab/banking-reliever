workspace "Programme Governance (CAP.STR.001.GOV)" "Define and evolve programme governance policies: eligibility rules, tier thresholds, co-decision protocols. Validates scoring model updates (ScoreModel.Updated from DAT.001.MOD) before any production deployment." {

    !identifiers hierarchical

    model {
        CAP_DAT_001_MOD = softwareSystem "Score Analytics Model" "Upstream capability (CAP.DAT.001.MOD)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.DAT.001.MOD"
            }
        }

        CAP_STR_001_GOV = softwareSystem "Programme Governance" "Define and evolve programme governance policies: eligibility rules, tier thresholds, co-decision protocols. Validates scoring model updates (ScoreModel.Updated from DAT.001.MOD) before any production deployment." {
            tags "capability-self" "level:L2" "zone:STR" "domain:generic"
            properties {
                "capability-id" "CAP.STR.001.GOV"
                "parent" "CAP.STR.001"
                "zoning" "STEERING"
                "owner" "Reliever Programme Directorate / Compliance Officer"
                "tech-stack" "stack-not-decided"
                "implementation-status" "not-scaffolded"
                "adr:ADR-BCM-FUNC-0015" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0015-L2-STR001-program-steering.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-PROD-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0005-dignity-as-functional-condition.md"
                "adr:ADR-PROD-0004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-PROD-0006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-PROD-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-PROD-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0003-scope-open-banking-protocol.md"
                "adr:ADR-PROD-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0001-service-offer-framing.md"
                "adr:ADR-TECH-STRAT-003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-003-api-contract-strategy.md"
                "adr:ADR-TECH-STRAT-002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-002-microservice-runtime.md"
                "adr:ADR-TECH-STRAT-006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-006-hosting-deployment.md"
                "adr:ADR-TECH-STRAT-005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-005-observability-governance.md"
                "adr:ADR-TECH-STRAT-007" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-007-identifier-strategy.md"
                "adr:ADR-TECH-STRAT-001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-001-event-infrastructure.md"
                "adr:ADR-TECH-STRAT-008" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-008-information-publication-model.md"
                "adr:ADR-TECH-STRAT-004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-004-data-referential-layer.md"
            }
            backend = container "Backend (planned)" "Backend (planned)" "stack-not-decided · not scaffolded yet" {
                tags "not-scaffolded" "tech:stack-not-decided"
            }
        }

        CAP_DAT_001_MOD -> CAP_STR_001_GOV.backend "SCORE MODEL UPDATED" "Business event subscription" "upstream-event"

        CAP_STR_001_GOV_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_STR_001_GOV.backend -> CAP_STR_001_GOV_downstream_consumers "GOVERNANCE POLICY UPDATED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_STR_001_GOV "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_STR_001_GOV "L2-Containers" {
            include *
            autoLayout lr
        }
        styles {
            element "capability-self" {
                background "#1168bd"
                color "#ffffff"
                shape RoundedBox
            }
            element "external-capability" {
                background "#999999"
                color "#ffffff"
                shape RoundedBox
            }
            element "implemented:mode-a" {
                background "#2e7d32"
                color "#ffffff"
            }
            element "implemented:stub" {
                background "#fbc02d"
                color "#000000"
            }
            element "implemented:bff" {
                background "#0288d1"
                color "#ffffff"
            }
            element "implemented:frontend" {
                background "#7b1fa2"
                color "#ffffff"
            }
            element "not-scaffolded" {
                background "#bdbdbd"
                color "#000000"
                border Dashed
            }
            element "ddd:aggregate" {
                background "#ffd54f"
                color "#000000"
                shape Hexagon
            }
            element "ddd:read-model" {
                background "#a5d6a7"
                color "#000000"
                shape Cylinder
            }
            element "ddd:policy" {
                background "#ce93d8"
                color "#000000"
            }
            element "ddd:publisher" {
                background "#ffab91"
                color "#000000"
                shape Pipe
            }
            element "zone:BSP" {
                background "#e8eaf6"
            }
            element "zone:SUP" {
                background "#fce4ec"
            }
            element "zone:REF" {
                background "#f1f8e9"
            }
            element "zone:CHN" {
                background "#e0f7fa"
            }
            element "zone:CHANNEL" {
                background "#e0f7fa"
            }
            element "zone:B2B" {
                background "#fff8e1"
            }
            element "zone:DAT" {
                background "#ede7f6"
            }
            element "zone:STR" {
                background "#efebe9"
            }
            element "level:L1" {
                strokeWidth 4
            }
            element "level:L2" {
                strokeWidth 2
            }
            relationship "upstream-event" {
                dashed true
                color "#ff7043"
            }
            relationship "downstream-event" {
                dashed true
                color "#42a5f5"
            }
        }
    }
}

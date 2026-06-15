workspace "Prescriber Arbitration (CAP.BSP.001.ARB)" "Handle manual overrides initiated by a prescriber via CHN.002.ACT: apply the human decision, monitor actual outcomes, and return control to the algorithm when reality confirms or refutes the prescriber's decision." {

    !identifiers hierarchical

    model {
        CAP_BSP_001_SCO = softwareSystem "Behavioural Scoring" "Upstream capability (CAP.BSP.001.SCO)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.SCO"
            }
        }
        CAP_BSP_001_TIE = softwareSystem "Tier Management" "Upstream capability (CAP.BSP.001.TIE)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.TIE"
            }
        }

        CAP_BSP_001_ARB = softwareSystem "Prescriber Arbitration" "Handle manual overrides initiated by a prescriber via CHN.002.ACT: apply the human decision, monitor actual outcomes, and return control to the algorithm when reality confirms or refutes the prescriber's decision." {
            tags "capability-self" "level:L2" "zone:BSP" "domain:core"
            properties {
                "capability-id" "CAP.BSP.001.ARB"
                "parent" "CAP.BSP.001"
                "zoning" "BUSINESS_SERVICE_PRODUCTION"
                "owner" "Reliever Programme Directorate"
                "tech-stack" "stack-not-decided"
                "implementation-status" "not-scaffolded"
                "adr:ADR-BCM-FUNC-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0005-L2-BSP001-behavioural-remediation.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-DOM-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0005-dignity-as-functional-condition.md"
                "adr:ADR-DOM-0004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-DOM-0006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-DOM-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-DOM-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0003-scope-open-banking-protocol.md"
                "adr:ADR-DOM-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0001-service-offer-framing.md"
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

        CAP_BSP_001_SCO -> CAP_BSP_001_ARB.backend "SCORE RECOMPUTED" "Business event subscription" "upstream-event"

        CAP_BSP_001_TIE -> CAP_BSP_001_ARB.backend "TIER OVERRIDE APPLIED" "Business event subscription" "upstream-event"

        CAP_BSP_001_ARB_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_BSP_001_ARB.backend -> CAP_BSP_001_ARB_downstream_consumers "ARBITRATION ALGORITHM REAFFIRMED, ARBITRATION OVERRIDE VALIDATED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_BSP_001_ARB "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_BSP_001_ARB "L2-Containers" {
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

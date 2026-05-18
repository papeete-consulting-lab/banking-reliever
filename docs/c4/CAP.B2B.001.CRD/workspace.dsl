workspace "CAP.B2B.001.CRD — Dedicated Card Management" "Drive the complete lifecycle of the Reliever dedicated card — issuance, activation, suspension, termination — in liaison with an approved issuing partner. Card usage rules (limits, categories) are synchronised with the current tier." {

    !identifiers hierarchical

    model {
        CAP_BSP_001_TIE = softwareSystem "CAP.BSP.001.TIE" "Upstream capability" {
            tags "external-capability"
        }
        CAP_BSP_002_ENR = softwareSystem "CAP.BSP.002.ENR" "Upstream capability" {
            tags "external-capability"
        }
        CAP_BSP_002_EXT = softwareSystem "CAP.BSP.002.EXT" "Upstream capability" {
            tags "external-capability"
        }

        CAP_B2B_001_CRD = softwareSystem "Dedicated Card Management" "Drive the complete lifecycle of the Reliever dedicated card — issuance, activation, suspension, termination — in liaison with an approved issuing partner. Card usage rules (limits, categories) are synchronised with the current tier." {
            tags "capability-self" "level:L2" "zone:B2B" "domain:generic"
            properties {
                "capability-id" "CAP.B2B.001.CRD"
                "parent" "CAP.B2B.001"
                "zoning" "EXCHANGE_B2B"
                "owner" "Financial Partnerships & Payments Team"
                "tech-stack" "stack-not-decided"
                "implementation-status" "not-scaffolded"
                "adr:ADR-BCM-FUNC-0011" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0011-L2-B2B001-financial-instrument.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-PROD-0005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0005-dignity-as-functional-condition.md"
                "adr:ADR-PROD-0004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-PROD-0006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-PROD-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-PROD-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0003-scope-open-banking-protocol.md"
                "adr:ADR-PROD-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0001-service-offer-framing.md"
                "adr:ADR-TECH-STRAT-003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-003-api-contract-strategy.md"
                "adr:ADR-TECH-STRAT-002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-002-microservice-runtime.md"
                "adr:ADR-TECH-STRAT-006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-006-hosting-deployment.md"
                "adr:ADR-TECH-STRAT-005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-005-observability-governance.md"
                "adr:ADR-TECH-STRAT-007" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-007-identifier-strategy.md"
                "adr:ADR-TECH-STRAT-001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-001-event-infrastructure.md"
                "adr:ADR-TECH-STRAT-008" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-008-information-publication-model.md"
                "adr:ADR-TECH-STRAT-004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-004-data-referential-layer.md"
            }
            backend = container "Backend (planned)" "Backend (planned)" "stack-not-decided · not scaffolded yet" {
                tags "not-scaffolded" "tech:stack-not-decided"
            }
        }

        CAP_BSP_001_TIE -> CAP_B2B_001_CRD.backend "EVT.BSP.001.TIER_DOWNGRADED, EVT.BSP.001.TIER_UPGRADED, RVT.BSP.001.TIER_DOWNGRADE_RECORDED, RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"

        CAP_BSP_002_ENR -> CAP_B2B_001_CRD.backend "EVT.BSP.002.BENEFICIARY_ENROLLED, RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"

        CAP_BSP_002_EXT -> CAP_B2B_001_CRD.backend "EVT.BSP.002.BENEFICIARY_EXITED, RVT.BSP.002.CASE_CLOSED" "RabbitMQ" "upstream-event"

        CAP_B2B_001_CRD_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the events emitted by this one." {
            tags "external-capability"
        }
        CAP_B2B_001_CRD.backend -> CAP_B2B_001_CRD_downstream_consumers "RVT.B2B.001.CARD_ISSUED, RVT.B2B.001.CARD_PERMANENTLY_CLOSED, RVT.B2B.001.CARD_PUT_IN_SERVICE, RVT.B2B.001.CARD_PUT_ON_HOLD" "RabbitMQ" "downstream-event"
    }

    views {
        systemContext CAP_B2B_001_CRD "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_B2B_001_CRD "L2-Containers" {
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

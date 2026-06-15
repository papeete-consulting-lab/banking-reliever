I'm an added functional domain-driven urbanist,  and I need you to build me a workflow with skills that lets me model first before implementing the adr.

I want to do a domain brainstorming session. So please create a domain brainstorming skill that goes into Socratic dialogue, ask me critical questions, and figure out what we really need to produce.  It should figure out what is and isn't in scope, present me with some alternatives, and do a deep modelling session with me, and it should not produce any code at all.
It should produce a one-line service offer (in a domain.md file under /domain-vision folder) that serves as the axis against which every decision thereafter will be made.

To architect how to respond to this service offer, I want to hold a strategic brainstorming session. So please create a strategic brainstorming skill that goes into Socratic dialogue, asks me critical questions, and figures out what we really need to produce based on what is in the product file.  It should figure out what is and isn't in scope, present me with some alternatives, and do a deep modelling session with me, and it should not produce any code at all. It should produce a strategic vision statement explaining the strategic capabilities involved. Strategic Capabilities should dive as much as 3 levels. The first one is the more important. It should be about business value and exclusively about business value. An example of L1 capabilities might be for an insurance company :
Stratégie & Pilotage de l'entreprise : donner une direction, arbitrer, mesurer la performance et assurer la pérennité de l’assureur.
Conception des Offres d’Assurance : Imaginer, structurer et faire évoluer des produits répondant aux besoins du marché et aux contraintes de risque.
Développement Commercial & Distribution : Acquérir des clients, développer les ventes et animer les canaux de distribution.
Souscription: Évaluer les risques, accepter ou refuser les affaires et formaliser les engagements contractuels.
Vie des contrats: assurer la continuité de la relation contractuelle tout au long de la durée de vie des polices.
Sinistres & Prestations : Honorer la promesse assurantielle en cas de réalisation du risque.
Relation & Expérience Client :Construire une relation durable et cohérente avec les clients à travers l’ensemble des points de contact.
Finance, Actuariat & Réassurance : Garantir l’équilibre économique, la solvabilité et la maîtrise des engagements.
It should lead to a single strategic-vision.md file under /strategic-vision folder containing all the information. 

Then I need a way to derive business capabilities for the information system from this strategic vision statement. So please create a business capabilities brainstorming skill that goes into Socratic dialogue, ask me critical questions, and figure out what we really need to produce.  It should figure out what is and isn't in scope, present me with some alternatives, and do a deep modelling session with me, and it should not produce any code at all. The mapping between L1 strategic capabilities and information system capabilities should be 1-1, but the need is different because we are now entering the world of Business Capability Map, as expressed in TOGAF. Every decision should be made in the context of the governance and urbanisation already taken. (Governance and urbanisation are given for context in ADR-BCM-GOV-* and ADR-BCM-URBA-*. Those files are read-only and are stored under adr) From this, I expect to create Functional ADRs explaining the decision made. I expect one ADR to explain roughly the level 1, and then one ADR per capability at L2. If we were to have capabilities at L3, one ADR per L3 would detail the whole picture.
Every ADR should be stored under /func-adr folder. I expect FUNC ADR to be coherent between them and with the URBA ADR already listed. This business capability map is extended because it follows the urbanisation decision record and thus goes beyond traditional business capability maps, borrowing a lot of concepts from event-driven architectures

Following this stage, I need everything translated into a world of reference to ensure we double-check the reference and can deterministically ensure everything is coherent. In order to do so, I need a  Business Capability Map writer skill. The production of YAML files should rely on previously produced ADRs and follow the templates defined in /templates. It should also check the coherence of its production using the /tools scripts available. 

Once I have the extended Business Capability Map defined in yaml files, I need to break those L2 or L3 capabilities in epics. The goal here is to achieve some form of global planning to support the business capability at L2 or L3. Each capability should have its own plan.md They should be stored under /plan/business-capability/plan.md. In order to do so, I need a plan skill.

Once I have a plan for each capability, I need to be able to generate tasks in order to produce applications that support the business capability. In order to do so, I need a task skill, that would generate tasks within /plan/business-capability/tasks. The tasks are about what is to be done using the implement-capability skill.

Finally, I need a last skill (code) that can trigger the coding of tasks.


--------
Product, strategic brainstorming, and business capabilities brainstorming are processes that follow each other. Please provide an agent in order to allow me to go through each of them sequentially. Provide also an agent that could spawn Business Capability Map writer for each business capability produced by the business capabilities brainstorming phase.
Any Business Capability produced in yaml should trigger another agent in order to generate plan. Any Plan modified should trigger task within another agent. Any created tasks should follow




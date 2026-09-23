# Oasis Graph CLI

This CLI manages the canonical graph data for `oasis-ontology`.

## Goals

- create, read, update, and delete ontology entities
- create, list, and delete ontology relations
- import workflow source files into canonical graph structure
- maintain document-backed entities with both markdown and JSON index data

## Supported Entity Types

- `Workflow`
- `WorkflowStepRef`
- `StepType`
- `StepVariant`
- `Protocol`
- `Instrument`
- `Process`
- `Knowledge`
- `Data`
- `Material`

## Supported Commands

- `init`
- `entity-create`
- `entity-get`
- `entity-list`
- `entity-update`
- `entity-delete`
- `relation-create`
- `relation-list`
- `relation-delete`
- `workflow-import`

## Entry

```bash
python graph_cli.py init
python graph_cli.py entity-list --type Process --text BODIPY
python graph_cli.py workflow-import --file sub-workflow-step-parameters/BODIPY---DAY1__加药孵育__3a202bba-f1fc-6af4-738d-10afee900175.json
```

## Data Layout

```text
graph/
  source/
    workflows/
  canonical/
    entities/
      workflows.json
      workflow_step_refs.json
      step_types.json
      step_variants.json
      protocols.json
      instruments.json
      processes/
        json/
          processes.json
        *.md
      knowledge/
        json/
          knowledge.json
        *.md
      data/
        json/
          data.json
        *.md
      materials/
        json/
          materials.json
        *.md
    relations/
      has_step.json
      refers_to_variant.json
      instance_of.json
      uses_protocol.json
      uses_instrument.json
      precedes.json
      workflow_use_material.json
      workflow_with_data.json
      process_produce_data.json
      guides.json
  schema/
  sync/
```

## Storage Strategy

- one JSON file per entity type
- one JSON file per relation type
- all canonical JSON files use `id -> object`

Document-backed entity types are:

- `Process`
- `Knowledge`
- `Data`
- `Material`

For these types:

- markdown stores the human-readable body
- JSON stores the canonical metadata index

## Automatic Relations From Workflow Import

`workflow-import` automatically creates:

- `Workflow -hasStep-> WorkflowStepRef`
- `WorkflowStepRef -refersToVariant-> StepVariant`
- `StepVariant -instanceOf-> StepType`
- `StepType -usesProtocol-> Protocol`
- `StepVariant -usesInstrument-> Instrument`

It does not automatically create:

- `Knowledge`
- `Knowledge -guides-> Process`

Those should be maintained manually as long-term knowledge objects.

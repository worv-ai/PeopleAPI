# PeopleAPI (omni.anim.people_api)

This repository is a fork of the Isaac Sim base extension "omni.anim.people". It exposes a
scripting-friendly API for controlling animated people while staying aligned with the upstream
behavior where possible.

## Goals

- Provide a stable, documented API for scripting and automation.
- Track upstream changes from "omni.anim.people" when relevant.

## Layout

- `exts/omni.anim.people_api/` - extension source code and data
- `exts/omni.anim.people_api/docs/README.md` - extension documentation
- `exts/omni.anim.people_api/omni/anim/people_api/examples/people_demo.py` - scripting example

## Quick Example

```python
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import omni.kit.app

# Enable the PeopleAPI extension before importing its modules.
ext_mgr = omni.kit.app.get_app().get_extension_manager()
ext_mgr.set_extension_enabled_immediate("omni.anim.people_api", True)

# Allow the extension to load.
for _ in range(10):
    simulation_app.update()

from omni.anim.people_api.scripts.utils import Utils

# Assumes a character named "Person_01" exists in the stage.
Utils.runtime_inject_command("Person_01", ["Person_01 Idle 1.0"], force_inject=True)

simulation_app.close()
```

## License

This repo contains components derived from "omni.anim.people". See
[exts/omni.anim.people_api/PACKAGE-LICENSES/omni.anim.people-LICENSE.md](exts/omni.anim.people_api/PACKAGE-LICENSES/omni.anim.people-LICENSE.md).

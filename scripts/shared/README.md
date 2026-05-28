# Shared Utilities

Core reusable modules for all scripts.

## Modules

### `resource_registry.py` - Central resource configuration
```python
from scripts.shared import get_resource, list_all_resources
resource = get_resource("pg-essay")  # Get by slug
all = list_all_resources()
```

### `cli_base.py` - Base class for resource scripts
```python
from scripts.shared import ResourceFetcherCLI

class MyFetcher(ResourceFetcherCLI):
    def get_default_output_dir_env(self) -> str:
        return "MY_DIR"
    
    def run_fetch(self, force: bool = False) -> dict:
        return {"fetched": 10, "failed": 0}

if __name__ == "__main__":
    import sys
    sys.exit(MyFetcher().main())
```

### `metadata_utils.py` - File I/O
```python
from scripts.shared import load_json, save_json, load_yaml

data = load_json(Path("file.json"))
config = load_yaml(Path("config.yaml"))
save_json(Path("out.json"), data)
```

### `output_formatters.py` - Console output
```python
from scripts.shared import OutputFormatter

formatter = OutputFormatter()
formatter.header("Title")
formatter.success("Done")
formatter.error("Error")
formatter.stats("Results", {"count": 10})
```

### `path_utils.py` - Path resolution
```python
from scripts.shared import get_project_root, get_artifacts_dir, get_metadata_dir

root = get_project_root()
artifacts = get_artifacts_dir()
metadata = get_metadata_dir()
```

## Adding New Resources

Edit `scripts/shared/resource_registry.py` and add to `RESOURCES` list:
```python
Resource(
    slug="my-resource",
    name="My Resource",
    output_dir="my_dir",
    env_var="MY_DIR",
    metadata_file="my_metadata.json",
    default_tags=["my-tag"],
)
```

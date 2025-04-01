### Getting Started

#### Using the provided `invoke` tasks
This project comes with a handful of helpful `invoke` tasks to help simplify and 
normalize your workflow. To see the available tasks, run 
```bash
inv --list
```
from your projects root directory.

The code for these tasks can be found in the `tasks` directory of this project.

#### Testing
> arguments can be passed to the commands run by tox by separating them from the first 
> part of the command using `--`. For example, I could run tests in parallel (using 
> `pytest-xdist`) with
> ```bash
> tox r -e py310 -- -n logical
> ```


#### Development Environment
The `tox.venv` task will initialize a pre-configured virtual environment!

To create the environment, run
```bash
inv tox.venv
```

This will create the directory `.venv`, then creates an environment within it. 

If you're using pycharm, make sure to choose the python executable from the created 
environment as your project interpreter in your project settings in pycharm.
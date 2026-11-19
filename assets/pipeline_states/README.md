# The shipped pipeline state lists

`nx2/make_game.py` (`ship_state_list`) merges the lists here into the game folder's `inhale_pipeline_states_shipped.bin`.
On a first start, the shader preparation builds those pipelines before the title, so the first visit to a place does not
stop to compile them (issue #1).

A list holds no game code or data. Each record is a pipeline's stage code keys (hashes of the game's shaders), the program
variant's hash, and the formats and draw state baked into the pipeline. The shaders themselves come from the player's own
game: `nx2/kirby_shaders.py` writes them into `inhale_shaders.bin` at the build.

- `contrib/<name>.bin.xz`: one list per source, and `<name>.md` beside it says where it comes from (who, GPU and driver,
  build, settings, route).
- To add one, take the game folder's `cache/inhale_pipeline_states.bin` after a play and run
  `python -I nx2/pipeline_states.py add <name> <list> --who ... --gpu ... --build ... --settings ... --route ...`.
  Then run `python -I nx2/pipeline_states.py check`.

The format and the tool are in `nx2/pipeline_states.py`.

- `train_muliturn_9390.json`: training data with sharegpt format
    ``` json
        [
            {
                "messages":[
                    {"role":"system", "content":"xxx"},
                    {"role":"user", "content":"<image>xxx"},
                    {"role": "assistant", "content": "xxx"},
                    ...
                ]
                "images":[
                    "",
                    ...
                ]
            }
        ]
    ```
- `agent_positions.json` : Simulator navigation failed, some navigation points were manually set to support evaluation
- `test_809.json`: 809 test data

> **Note**: Follow the registration method of dataset in [LLaMA-Factory](https://github.com/iGangao/LLaMA-Factory/blob/embodied-reasoner/data/README.md): please **make sure** to add a *dataset description* in [`dataset_info.json`](https://github.com/iGangao/LLaMA-Factory/blob/embodied-reasoner/data/dataset_info.json) and specify `dataset: dataset_name` before training to use it.
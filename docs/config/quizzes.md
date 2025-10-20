# Quiz Datasets


Quizzes use the evaluation dataset entries (see the
[schema]("https://schema.pydantic.dev/evals/dataset.json")).


## Room Configuration

- Room configurations get a new key, `quizzes`, with a value which
  is a mapping defining quizes which can be run in the room
  (see `rooms/README.md`).

## API

### `GET /api/v1/rooms`

Room config entries in the response include the value of `quizzes` (a
list of mappings).


### `GET /api/v1/rooms/{room_id}`

Response includes  the value of `quizzes` (a list of mappings).


### `GET /api/v1/rooms/{room_id}/quiz/{quiz_id}`

Fetch the quiz.  Returns a mapping for the quiz with a list of questions:

```
{
    "id": "<quiz_id>",
    "questions": [
        {
            "uuid": "<question_uuid>",
            "inputs": "What color is the sky? (QA)",
            "metadata": {
                "type": "qa"
            }
        },
        {
            "uuid": "<question_uuid>",
            "inputs": "The color of the sky is _____",
            "metadata": {
                "type": "fill-blank"
            }
        },
        {
            "uuid": "<question_uuid>",
            "inputs": "Is the sky blue?",
            "metadata": {
                "type": "multiple-choice",
                "options": {
                    "true",
                    "false"
                }
            }
        },
        {
            "uuid": "<question_uuid>",
            "inputs": "What color is the sky? (MC)",
            "metadata": {
                "type": "multiple-choice",
                "options": {
                    "red",
                    "green",
                    "blue"
                }
            }
        },
    ...
    ]
}
```

- `question-type` is one of `"qa"`, `"fill-blank"`, or `"multiple-choice"`

- Questions of type `"multiple-choice"` contain an additional entry,
  `"options"` in their metadata, whose value is a list of strings.

### `POST /api/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}`

Check an anwer.  Client should send the answer entered / selected by the
user as a `text/plain` body.  For a correct answer, returns:

```
{
    "correct": "true"
}
```

For a incorrect answer, returns:
```
{
    "correct": "false"
    "expected_output": "<expected_output>"
}
```

(Later, this response might include more information, such as a citation).

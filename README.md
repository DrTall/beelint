# beelint
Verifies you are on track to succeed at your Beeminder goals.

Beelint inspects your goals for "violations" which today means goals which are currently due on a day that is bad/wrong/inconvienent. For example, some goals are weekends only and some days you are on vacation. Beelint will complain about these problems and force you to fix them.

## Setup
1. Clone this repo.
2. Fill in `secrets.py` with your info. The Google Calendar API step is optional.
3. Compile `config.proto` with `protoc -I=. --python_out=. config.proto`.
4. Fill in `config` according to your needs. There are some examples in `example_config`. If you want the nuts and bolts you can refer to `config.proto` itself.


"""Ancient Rome, ages 9–11. Quest codes match the curriculum blueprint."""

from app.curriculum.shape import (
    course,
    half,
    ladder,
    mcq,
    quest,
    rubric,
    standard,
    traps,
    unit,
)

COMPETENCIES = [
    ("myth-evidence", "Tell a founding myth apart from an archaeological clue."),
    ("geography", "Explain how the Alps and the Tiber shaped Rome."),
    ("anti-monarchy", "Explain why Romans rejected kings after Tarquin."),
    ("shared-power", "Explain how two consuls and a veto limit one ruler."),
    ("public-law", "Explain why laws posted in public protect ordinary people."),
    ("republic-war", "Explain how the Republic survived a long war and expanded."),
    ("generals", "Explain what happens when armies follow a general instead of the laws."),
    ("empire", "Explain how engineering held the empire together and why it split."),
]


def _two_captain() -> dict:
    """ROM-U2-Q1 written beats."""
    beats = [
        {
            "role": "mystery_hook",
            "bloom_level": "analyze",
            "cognitive_load": "medium",
            "prompt": (
                "Rome elected two Consuls for only 1 year who could shout VETO at each other. "
                "What is one big advantage and one messy problem of two equal captains?"
            ),
            "rubric": rubric(
                ("advantage", "Names an advantage that stops one bully or a king.", 50),
                ("problem", "Names deadlock or arguing in an emergency.", 50),
            ),
            "misconception_map": traps(
                (
                    "solo-boss",
                    "One boss is always safer because someone has to decide.",
                    "The veto is the point: neither captain can become a king.",
                )
            ),
            "hint_ladder": ladder(
                "What happens when an enemy army attacks and the Consuls disagree?",
                "Picture two kids holding one video-game controller.",
                "Fill in the blank: Two consuls can stop a ____ from ruling alone, but they can also ____ when they disagree.",
            ),
            "widget": None,
        },
        {
            "role": "interactive_toy",
            "bloom_level": "understand",
            "cognitive_load": "low",
            "prompt": "How did Plebeians peacefully win fair rights from Patricians in 494 BCE?",
            "rubric": rubric(
                (
                    "walkout",
                    "The peaceful win was the walkout: they left Rome and camped on a hill on strike.",
                    100,
                )
            ),
            "misconception_map": traps(
                (
                    "external",
                    "Fair rights came from a foreign army arresting the Senators.",
                    "The Plebeians used their own labor strike, not Greece.",
                ),
                (
                    "wealth",
                    "Fair rights were bought with a pile of gold.",
                    "They won by withholding work, not by paying.",
                ),
            ),
            "hint_ladder": ladder(
                "Who left the city, and did they bring an army from somewhere else?",
                "A team can win a rule change by refusing to play, not by paying the coach.",
                "Fill in: They ____ out of Rome and camped on a hill.",
            ),
            "widget": mcq(
                "How did Plebeians peacefully win fair rights from Patricians in 494 BCE?",
                [
                    (
                        "greece",
                        "Asked Greece to arrest Senators.",
                        "That is an outside army. The Plebeians did not call Greece.",
                    ),
                    (
                        "walkout",
                        "Walked out of Rome and camped on a hill on strike.",
                        "",
                    ),
                    (
                        "gold",
                        "Paid a million gold coins.",
                        "That is a wealth trap. They did not buy the new rights.",
                    ),
                ],
                "walkout",
                misconception="Look for a peaceful strike, not a foreign arrest or a pile of gold.",
            ),
        },
        {
            "role": "diagnostic_gate",
            "bloom_level": "analyze",
            "cognitive_load": "medium",
            "prompt": (
                "Why did carving laws onto the Twelve Bronze Tables in the public marketplace "
                "protect regular citizens compared with secret laws inside rich judges' heads?"
            ),
            "rubric": rubric(
                ("secret", "Secret laws let judges cheat or favor rich friends.", 50),
                (
                    "public",
                    "Public written laws force everyone to follow the same visible rules.",
                    50,
                ),
            ),
            "misconception_map": traps(
                (
                    "memory",
                    "A judge who remembers the law is as fair as a law posted in the market.",
                    "A hidden rule can change for a rich friend. A posted rule cannot.",
                )
            ),
            "hint_ladder": ladder(
                "Who can check a law that only the judge can see?",
                "A playground rule on the fence is harder to cheat than a rule the captain whispers.",
                "Fill in: Secret laws let judges ____. Posted laws make the rule ____.",
            ),
            "widget": None,
        },
        {
            "role": "feynman_flip",
            "bloom_level": "evaluate",
            "cognitive_load": "high",
            "prompt": (
                "Bumbling Centurion Bot claims one ruler for life with secret laws is better. "
                "Correct the bot by teaching the Two-Consul veto and the Twelve Tables."
            ),
            "rubric": rubric(
                ("veto", "Teaches the two-consul veto as a check on one ruler.", 50),
                ("tables", "Teaches the Twelve Tables as laws ordinary people can see.", 50),
            ),
            "misconception_map": traps(
                (
                    "lifetime",
                    "One ruler for life with secret laws is kinder because decisions are fast.",
                    "Speed without a veto or a public law is how Tarquin ruled.",
                )
            ),
            "hint_ladder": ladder(
                "What can the second consul shout, and where were the laws posted?",
                "Two team captains who can block each other, plus the rulebook on the fence.",
                "Teach the bot: two consuls can ____, and the Twelve Tables were ____ in public.",
            ),
            "widget": None,
        },
    ]
    return quest(
        "ROM-U2-Q1",
        "The Two-Captain Rule: Consuls and Veto Power",
        "core",
        ["ROM-U1-BOSS"],
        ["shared-power", "public-law"],
        "At dinner, ask what is better about two captains who can veto each other than one captain for life.",
        beats,
    )


def rome_course() -> dict:
    return course(
        "rome",
        "Ancient Rome: From Seven Hills to the Fall of the Empire",
        "9-11",
        "NCSS C3 / UK KS2",
        COMPETENCIES,
        [
            unit(
                1,
                "Myth, Geography and The Last King",
                "Geography shielded Rome, and bad kings made Romans hate crowns forever.",
                "A founding story and a buried clue answer different questions, and the land around Rome did real work. Tarquin's solo lifetime power is why the next unit refuses another crown.",
                [
                    standard(
                        "ROM-U1-Q1",
                        "The Wolf Myth vs. The Archaeology Clue",
                        "core",
                        [],
                        ["myth-evidence"],
                        "Ask which tells you more when they disagree: the wolf story, or a wall dug out of the ground.",
                        hook="Romulus and the wolf is a story Romans liked to tell. A dated wall under the Forum is a clue you can check. What is one thing only the story can give you, and one thing only the buried wall can give you?",
                        hook_pair=(
                            ("story", "The myth can give a meaning or a feeling about how Rome wanted to begin."),
                            ("clue", "The wall can give a checkable clue about what was actually built."),
                        ),
                        hook_hints=(
                            "Can you dig up a feeling, or only a thing someone left behind?",
                            "A team song tells you what the team loves. A trophy case tells you what they won.",
                            "The story gives ____. The buried wall gives ____.",
                        ),
                        hook_trap=(
                            "same",
                            "A famous story and a buried wall prove the same kind of fact.",
                            "A story can be loved and still not be evidence.",
                        ),
                        toy_prompt="Which of these is an archaeological clue, not the wolf myth?",
                        choices=[
                            ("wolf", "The wolf nursed the twins.", "That is the myth, not a thing dug from the ground."),
                            ("wall", "A wall and pottery dated to early Rome.", ""),
                            ("poem", "A later poem that says the wolf was real.", "A poem is still a story, even if it sounds sure."),
                        ],
                        answer="wall",
                        toy_trap=(
                            "poem",
                            "A poem that repeats the myth becomes evidence.",
                            "Repeating a story does not turn it into a clue you can date.",
                        ),
                        gate="Why can a city keep telling the wolf story and still trust the buried wall more when the story and the wall disagree?",
                        gate_pair=(
                            ("keep", "The story can stay as a meaning the city likes."),
                            ("trust", "The wall is trusted more for what happened because it can be checked."),
                        ),
                        gate_hints=(
                            "Which one can a different person measure again?",
                            "You can love a campfire story and still follow the map.",
                            "Keep the story for ____. Trust the wall for ____.",
                        ),
                        gate_trap=(
                            "erase",
                            "If the wall is real, the story has to be thrown out.",
                            "The quest is about what each one is for, not about banning stories.",
                        ),
                        flip="Legend Bot says the wolf story proves the buried wall is fake. Teach the bot the difference between a myth and an archaeological clue.",
                        flip_pair=(
                            ("myth", "A myth is a story about meaning, not a dated object."),
                            ("clue", "An archaeological clue is something you can check in the ground."),
                        ),
                        flip_hints=(
                            "Does the bot think a story and a wall are the same kind of proof?",
                            "A mascot is not the same as the bricks of the clubhouse.",
                            "Tell the bot: the wolf is a ____, and the wall is a ____.",
                        ),
                        flip_trap=(
                            "proves",
                            "A loved story can cancel a dated find.",
                            "Affection for a story is not a test of the wall.",
                        ),
                    ),
                    standard(
                        "ROM-U1-Q2",
                        "Why Pick Italy? The Alps Shield and Tiber Highway",
                        "core",
                        ["ROM-U1-Q1"],
                        ["geography"],
                        "Ask how a mountain shield and a river highway could help the same city.",
                        hook="The Alps stand like a shield to the north. The Tiber runs like a highway to the sea. What is one advantage of the shield, and one advantage of the river?",
                        hook_pair=(
                            ("shield", "The Alps make an invasion from the north harder."),
                            ("highway", "The Tiber moves people, trade, and salt."),
                        ),
                        hook_hints=(
                            "What does a shield stop, and what does a road carry?",
                            "A fence keeps a rush out. A path lets friends and food in.",
                            "The Alps help by ____. The Tiber helps by ____.",
                        ),
                        hook_trap=(
                            "same-job",
                            "The river and the mountains do the same job.",
                            "One blocks. One connects.",
                        ),
                        toy_prompt="Why did the Tiber help Rome grow?",
                        choices=[
                            ("block", "It blocked every visitor.", "That is the Alps' job, not the river's."),
                            ("highway", "It was a highway for boats, trade, and salt.", ""),
                            ("flat", "It made the Alps disappear.", "A river does not remove a mountain range."),
                        ],
                        answer="highway",
                        toy_trap=(
                            "shield-river",
                            "The Tiber's main gift was keeping people out.",
                            "The river's gift was movement.",
                        ),
                        gate="How did the Alps and the Tiber together make Rome safer and busier than a village with neither?",
                        gate_pair=(
                            ("safer", "The Alps made a northern attack harder, so the city was safer."),
                            ("busier", "The Tiber brought trade, so the city was busier."),
                        ),
                        gate_hints=(
                            "Safety and traffic are two different gifts. Which landform gives which?",
                            "A fort on a trade road gets both guards and customers.",
                            "Safer because of the ____. Busier because of the ____.",
                        ),
                        gate_trap=(
                            "either",
                            "Either the mountains or the river would have been enough on its own.",
                            "The quest wants the pair.",
                        ),
                        flip="Map Bot thinks a river is only a danger and a mountain is only a wall that stops trade. Teach the bot the shield and the highway.",
                        flip_pair=(
                            ("alps", "The Alps are a shield against invasion."),
                            ("tiber", "The Tiber is a highway for trade."),
                        ),
                        flip_hints=(
                            "Which landform stops an army, and which one carries a boat?",
                            "A helmet is not a shopping bag.",
                            "Teach: Alps ____, Tiber ____.",
                        ),
                        flip_trap=(
                            "danger",
                            "Water is only a flood, so Rome would have grown faster without the Tiber.",
                            "The river's trade is why the site was worth defending.",
                        ),
                    ),
                    standard(
                        "ROM-U1-Q3",
                        "Tarquin the Proud and Why Rome Fired Its Kings",
                        "core",
                        ["ROM-U1-Q2"],
                        ["anti-monarchy"],
                        "Ask why a cruel king who rules for life would make a city hate crowns.",
                        hook="Tarquin the Proud ruled alone for life and hurt people who could not vote him out. What is one reason Romans would hate crowns after a king like that?",
                        hook_pair=(
                            ("abuse", "He used solo power to hurt people."),
                            ("lifetime", "Nobody could end his rule at the end of a year."),
                        ),
                        hook_hints=(
                            "What could the city do if the king was cruel and the job never ended?",
                            "A captain who never has to hand over the whistle can ignore the team.",
                            "They hated crowns because one person could ____ for ____.",
                        ),
                        hook_trap=(
                            "wealth",
                            "Rome fired its kings because the treasury was empty.",
                            "The grievance was unchecked lifetime power.",
                        ),
                        toy_prompt="Why did Rome fire its kings?",
                        choices=[
                            ("greece", "They wanted a king from Greece.", "That brings in an outsider. Rome was rejecting kings."),
                            ("tarquin", "Tarquin abused solo lifetime power.", ""),
                            ("gold", "They ran out of gold crowns.", "A missing crown is not why they hated kingship."),
                        ],
                        answer="tarquin",
                        toy_trap=(
                            "foreign-king",
                            "Firing a bad king means hiring a foreign one.",
                            "They were done with the office, not shopping for a new one.",
                        ),
                        gate="What is the difference between a leader the city can replace and a king who rules for life?",
                        gate_pair=(
                            ("replace", "A replaceable leader can be removed when the term ends or the city says no."),
                            ("life", "A king for life can keep hurting people with no vote to stop him."),
                        ),
                        gate_hints=(
                            "Who gets to say the job is over?",
                            "A substitute teacher leaves on Friday. A king who owns the school does not.",
                            "Replaceable means ____. For life means ____.",
                        ),
                        gate_trap=(
                            "title",
                            "The only difference is the word king.",
                            "The difference is whether the power ends.",
                        ),
                        flip="Crown Bot says one king for life is kinder because the city always knows who is in charge. Teach the bot what Tarquin did with that kind of power.",
                        flip_pair=(
                            ("tarquin", "Tarquin used lifetime power to abuse people who could not remove him."),
                            ("refuse", "Rome's answer was to refuse another crown."),
                        ),
                        flip_hints=(
                            "Did knowing the king's name protect the people he hurt?",
                            "A bully with a permanent badge is still a bully.",
                            "Teach: Tarquin ____, so Rome ____.",
                        ),
                        flip_trap=(
                            "order",
                            "Any permanent ruler is kinder than a city that argues.",
                            "The argument is the check Tarquin did not have.",
                        ),
                    ),
                    standard(
                        "ROM-U1-BOSS",
                        "Unit 1 Capstone — Vote Out the King",
                        "capstone",
                        ["ROM-U1-Q3"],
                        ["anti-monarchy", "geography"],
                        "Ask your child to give one land reason and one king reason for voting out crowns.",
                        hook="You are in the assembly. Using the land around Rome and the story of Tarquin, what is one geography reason and one king reason to vote against crowns?",
                        hook_pair=(
                            ("land", "Uses the Alps or the Tiber as a reason Rome could stand without a king."),
                            ("king", "Uses Tarquin's abuse of lifetime power as a reason to refuse another crown."),
                        ),
                        hook_hints=(
                            "You need one reason from the map and one from the last king.",
                            "A team can point at its field and at a bad captain.",
                            "From the land: ____. From Tarquin: ____.",
                        ),
                        hook_trap=(
                            "one",
                            "One reason, either land or king, is the whole vote.",
                            "The capstone wants both.",
                        ),
                        toy_prompt="Which vote matches this unit?",
                        choices=[
                            ("crown", "Crown a stronger king.", "That repeats the office the unit is rejecting."),
                            ("share", "Share power so no one rules for life.", ""),
                            ("foreign", "Ask a foreign army to pick the king.", "That hands the choice to an outsider."),
                        ],
                        answer="share",
                        toy_trap=(
                            "stronger",
                            "A harsher king would fix a bad king.",
                            "The problem was the unchecked crown, not a weak one.",
                        ),
                        gate="Write the two reasons you would say out loud before the vote.",
                        gate_pair=(
                            ("aloud-land", "Says a geography reason out loud."),
                            ("aloud-king", "Says Tarquin's lifetime abuse out loud."),
                        ),
                        gate_hints=(
                            "Say them as two sentences a neighbor could repeat.",
                            "One sentence about the map. One sentence about the king.",
                            "I vote no because the land ____, and because Tarquin ____.",
                        ),
                        gate_trap=(
                            "secret",
                            "The reasons should stay inside the speaker's head.",
                            "A vote in public needs reasons other people can hear.",
                        ),
                        flip="A friend still wants a king. Teach them, with the land and with Tarquin, why this unit votes the crown out.",
                        flip_pair=(
                            ("teach-land", "Uses geography in the teaching."),
                            ("teach-king", "Uses Tarquin's abuse in the teaching."),
                        ),
                        flip_hints=(
                            "Your friend needs both reasons, not a slogan.",
                            "Show the shield and the highway, then the king who would not leave.",
                            "Teach: the land ____, and Tarquin ____.",
                        ),
                        flip_trap=(
                            "slogan",
                            "Saying kings are bad is enough teaching.",
                            "The teaching has to use this unit's two ideas.",
                        ),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                2,
                "The Roman Republic and Checks on Power",
                "Sharing power and writing laws in public protects regular citizens.",
                "King Tarquin abused solo lifetime power. Two consuls, a veto, and laws carved in public are how the Republic tried to protect ordinary people after that.",
                [
                    _two_captain(),
                    standard(
                        "ROM-U2-Q2",
                        "The Plebeian Walkout and The Twelve Bronze Tables",
                        "core",
                        ["ROM-U2-Q1"],
                        ["public-law", "shared-power"],
                        "Ask why leaving the city, and then posting the laws, could protect people who were not rich.",
                        hook="In 494 BCE the Plebeians walked out and camped on a hill. What pressure did that put on the Patricians, and why was it peaceful?",
                        hook_pair=(
                            ("pressure", "The city lost the workers and soldiers it needed."),
                            ("peaceful", "They refused to work instead of attacking the Senate."),
                        ),
                        hook_hints=(
                            "What stops getting done if the workers leave?",
                            "A team that sits out the game forces a rule talk without a fight.",
                            "The pressure was ____. It was peaceful because ____.",
                        ),
                        hook_trap=(
                            "riot",
                            "The only way to win rights was to burn the Senate.",
                            "This quest's win was a strike.",
                        ),
                        toy_prompt="What did the walkout win toward, before the laws were posted?",
                        choices=[
                            ("war", "A war against Greece.", "The strike was inside Rome."),
                            ("voice", "A voice for Plebeians who had been shut out of the rules.", ""),
                            ("gold", "A payment of a million gold coins.", "They were not buying the law."),
                        ],
                        answer="voice",
                        toy_trap=(
                            "payoff",
                            "The walkout was a demand for cash.",
                            "The demand was a share of the rules.",
                        ),
                        gate="Why did carving the Twelve Tables in the marketplace protect regular citizens more than leaving the laws in rich judges' memories?",
                        gate_pair=(
                            ("cheat", "Secret laws let judges favor rich friends."),
                            ("same", "A public text makes the same rule visible to everyone."),
                        ),
                        gate_hints=(
                            "Who can argue with a law they are allowed to read?",
                            "A rule on the gym wall is harder to change for one friend.",
                            "Hidden laws let judges ____. Posted laws make the rule ____.",
                        ),
                        gate_trap=(
                            "trust",
                            "A good judge's memory is safer than a public text.",
                            "Memory can bend. Bronze in the market cannot, quietly.",
                        ),
                        flip="Tribune Bot says the strike was rude and secret laws are faster. Teach the walkout and the Twelve Tables.",
                        flip_pair=(
                            ("strike", "Teaches the walkout as a peaceful strike."),
                            ("tables", "Teaches the Tables as public laws."),
                        ),
                        flip_hints=(
                            "Speed for whom, if only the judge knows the rule?",
                            "Sitting out the game, then hanging the rule where both teams can see it.",
                            "The walkout ____. The Tables ____.",
                        ),
                        flip_trap=(
                            "rude",
                            "Any strike is just bad manners, so it cannot change a law.",
                            "This strike changed who the law was for.",
                        ),
                    ),
                    standard(
                        "ROM-U2-Q3",
                        "Hannibal's Elephants and The Punic Wars",
                        "core",
                        ["ROM-U2-Q2"],
                        ["republic-war"],
                        "Ask how a Republic with shared power could survive a long war and come out larger.",
                        hook="Hannibal crossed the Alps with elephants and beat Roman armies in Italy. What is one reason that invasion was terrifying, and one reason Rome did not collapse in a single battle?",
                        hook_pair=(
                            ("terror", "An army with elephants inside Italy threatened the city itself."),
                            ("held", "Rome could raise new armies and keep fighting after a loss."),
                        ),
                        hook_hints=(
                            "A scary invasion and a city that can try again are two different facts.",
                            "One bad game does not end a season if the club can field another team.",
                            "Terrifying because ____. Rome held because ____.",
                        ),
                        hook_trap=(
                            "one-loss",
                            "The first lost battle ended the Republic.",
                            "The long war is the point.",
                        ),
                        toy_prompt="What did the Punic Wars do to Rome's power by the end?",
                        choices=[
                            ("ended", "They ended Rome and put Hannibal on the throne.", "Rome survived and Hannibal did not become king."),
                            ("larger", "Rome survived and came out with a larger Mediterranean empire.", ""),
                            ("elephants", "They replaced the consuls with elephants.", "The elephants were Hannibal's army, not Rome's government."),
                        ],
                        answer="larger",
                        toy_trap=(
                            "throne",
                            "A brilliant invader automatically becomes the new king.",
                            "Winning battles in Italy did not hand him the Republic.",
                        ),
                        gate="How could shared power help a city survive a long war better than a single king whose death or panic ends the command?",
                        gate_pair=(
                            ("replace", "Consuls and the Senate could keep raising command after a loss."),
                            ("risk", "One king's capture or fear would have put the whole command in one person."),
                        ),
                        gate_hints=(
                            "What happens to a team if the only coach is captured?",
                            "Two captains and a bench of substitutes can play the next match.",
                            "Shared power ____. One king ____.",
                        ),
                        gate_trap=(
                            "genius",
                            "Only a genius king can survive a long war.",
                            "Rome's survival here is about institutions that outlast one person.",
                        ),
                        flip="Scout Bot says one lost battle with elephants means the Republic's laws failed. Teach the bot what the long war actually did to Rome.",
                        flip_pair=(
                            ("survive", "Rome survived losses inside Italy."),
                            ("grew", "The wars left Rome larger across the Mediterranean."),
                        ),
                        flip_hints=(
                            "A lost battle and a lost war are not the same.",
                            "A team can lose the home game and still win the season, then own more fields.",
                            "Rome ____ the losses, and afterward it was ____.",
                        ),
                        flip_trap=(
                            "failed",
                            "Any loss proves the government was fake.",
                            "The Republic absorbed losses and expanded.",
                        ),
                    ),
                    standard(
                        "ROM-U2-BOSS",
                        "Unit 2 Capstone — Debate in the Roman Forum",
                        "capstone",
                        ["ROM-U2-Q3"],
                        ["shared-power", "public-law"],
                        "Ask your child to argue, as if in the Forum, for two consuls and public laws.",
                        hook="You have the Forum floor. Give one reason for two consuls who can veto, and one reason for laws posted where ordinary people can read them.",
                        hook_pair=(
                            ("consuls", "Two consuls with a veto stop one person from ruling like a king."),
                            ("posted", "Posted laws stop secret rules that favor the rich."),
                        ),
                        hook_hints=(
                            "The Forum wants both the captains and the bronze tables.",
                            "Two referees, and a rulebook the crowd can see.",
                            "Consuls help because ____. Posted laws help because ____.",
                        ),
                        hook_trap=(
                            "either",
                            "Either consuls or public laws alone finish the argument.",
                            "The debate wants the pair.",
                        ),
                        toy_prompt="Which speech belongs in this Forum debate?",
                        choices=[
                            ("king", "Bring back one king so wars are faster.", "That undoes the unit's check on solo power."),
                            ("both", "Keep two consuls and keep the laws in public.", ""),
                            ("secret", "Let judges keep the laws in their heads so trials are quick.", "Speed that hides the rule is the problem the Tables fixed."),
                        ],
                        answer="both",
                        toy_trap=(
                            "speed",
                            "The fastest government is the one this unit wants.",
                            "The unit trades a little speed for a check and a public rule.",
                        ),
                        gate="A rival says vetoes cause deadlock and public laws insult the judges. Answer both complaints with this unit's idea.",
                        gate_pair=(
                            ("deadlock", "Names deadlock as the cost, and still defends the veto as a check on a bully."),
                            ("judges", "Defends public laws because secret laws let judges favor friends."),
                        ),
                        gate_hints=(
                            "Do not pretend the veto is free. Say what it buys.",
                            "A shared controller can freeze the game, and that is still better than one kid owning it.",
                            "The veto costs ____ but stops ____. Public laws stop judges from ____.",
                        ),
                        gate_trap=(
                            "deny",
                            "The right answer is to say vetoes never cause arguments.",
                            "The quest wants the cost and the protection.",
                        ),
                        flip="Forum Bot wants one ruler and secret laws back. Teach the bot, as a short speech, why the Republic keeps both checks.",
                        flip_pair=(
                            ("speech-veto", "The speech teaches the veto."),
                            ("speech-law", "The speech teaches public laws."),
                        ),
                        flip_hints=(
                            "A speech can be four sentences and still hold both ideas.",
                            "Talk to the bot the way you would talk to the crowd.",
                            "Keep the veto because ____. Keep public laws because ____.",
                        ),
                        flip_trap=(
                            "insult",
                            "The bot is rude, so the lesson is to insult it back.",
                            "The lesson is the two checks.",
                        ),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                3,
                "Julius Caesar and The Fall of the Republic",
                "When armies are loyal to generals over laws, democracy collapses.",
                "The Republic's checks only work if armies obey the laws rather than a general. When soldiers follow a person across the Rubicon, the shared power from the last unit collapses.",
                [
                    standard(
                        "ROM-U3-Q1",
                        "Generals vs. The Senate",
                        "core",
                        ["ROM-U2-BOSS"],
                        ["generals"],
                        "Ask what breaks when soldiers obey a general instead of the Senate's laws.",
                        hook="A consul's power was supposed to end. A successful general could pay and lead the same soldiers for years. What is one danger when an army loves the general more than the law?",
                        hook_pair=(
                            ("person", "The army's loyalty sticks to a person."),
                            ("law", "The Senate's laws lose the force that made consuls step down."),
                        ),
                        hook_hints=(
                            "Who do the soldiers listen to if the pay and the victories come from one man?",
                            "A team that obeys the star player instead of the referee.",
                            "Loyalty to the general means ____. The law then ____.",
                        ),
                        hook_trap=(
                            "always",
                            "A winning general is automatically the law.",
                            "The danger is the army treating him as the law.",
                        ),
                        toy_prompt="What threatens the Republic when a general's army is loyal to him?",
                        choices=[
                            ("maps", "Soldiers learn too much geography.", "Skill is not the threat. Loyalty is."),
                            ("person", "The army may follow the general against the Senate.", ""),
                            ("vote", "Plebeians get a second vote.", "A second vote is not what a private army does."),
                        ],
                        answer="person",
                        toy_trap=(
                            "skill",
                            "Being good at war is itself the collapse.",
                            "The collapse is personal loyalty backed by soldiers.",
                        ),
                        gate="Why can shared offices and posted laws fail if the soldiers in the field do not obey them?",
                        gate_pair=(
                            ("paper", "Laws and offices on paper do not move an army."),
                            ("obey", "The checks work only if the people with weapons follow them."),
                        ),
                        gate_hints=(
                            "Who has the swords when the Senate sends a letter?",
                            "A rulebook cannot tackle. The players have to follow it.",
                            "Paper checks fail when ____. They work when soldiers ____.",
                        ),
                        gate_trap=(
                            "speech",
                            "A good speech in the Senate controls every camp.",
                            "The camp has to obey the speech.",
                        ),
                        flip="Camp Bot says a beloved general is just a consul with better luck. Teach the bot the difference between a term of office and an army that belongs to a person.",
                        flip_pair=(
                            ("term", "A consul's office is supposed to end."),
                            ("army", "A personal army can ignore that ending."),
                        ),
                        flip_hints=(
                            "Luck does not explain who the soldiers will march for.",
                            "A captain's badge expires. A private gang does not.",
                            "The office ____. The personal army ____.",
                        ),
                        flip_trap=(
                            "luck",
                            "Popularity and legal power are the same thing.",
                            "Popularity plus soldiers is a different power.",
                        ),
                    ),
                    standard(
                        "ROM-U3-Q2",
                        "Crossing the Rubicon",
                        "core",
                        ["ROM-U3-Q1"],
                        ["generals"],
                        "Ask why bringing an army across the Rubicon was a choice to fight the Republic, not a trip home.",
                        hook="Roman generals were supposed to leave their armies before crossing the Rubicon into Italy. Caesar crossed with his soldiers. What rule did that break, and what did it tell the Senate?",
                        hook_pair=(
                            ("rule", "He brought an army into Italy, which a returning general was not allowed to do."),
                            ("message", "It told the Senate he would use soldiers rather than accept the law."),
                        ),
                        hook_hints=(
                            "Was the river the problem, or the army on the wrong side of it?",
                            "Walking into the gym with your own team after the referee said leave the equipment outside.",
                            "The broken rule was ____. The Senate heard ____.",
                        ),
                        hook_trap=(
                            "swim",
                            "The crime was getting wet in the river.",
                            "The crime was the armed crossing.",
                        ),
                        toy_prompt="What did crossing the Rubicon with an army mean?",
                        choices=[
                            ("parade", "A legal parade home.", "A parade would have left the army behind."),
                            ("war", "A choice to use the army against the Republic's rule.", ""),
                            ("map", "A new name for the Alps.", "The Rubicon is the boundary, not a mountain."),
                        ],
                        answer="war",
                        toy_trap=(
                            "legal",
                            "Any famous general may bring troops into the capital.",
                            "The ban on that march was the point.",
                        ),
                        gate="Why is an army that crosses a legal boundary more dangerous to a republic than a general who argues in the Senate?",
                        gate_pair=(
                            ("force", "The army can force a result the vote did not give."),
                            ("speech", "An argument in the Senate still stays inside the law."),
                        ),
                        gate_hints=(
                            "Which one can ignore a no?",
                            "Shouting from the bench is not the same as bringing bats into the meeting.",
                            "The army ____. The Senate argument ____.",
                        ),
                        gate_trap=(
                            "words",
                            "Words and soldiers put the same pressure on a law.",
                            "Soldiers change the kind of pressure.",
                        ),
                        flip="River Bot says Caesar was only going home. Teach the bot what the soldiers made that crossing mean.",
                        flip_pair=(
                            ("not-home", "Going home would have meant leaving the army."),
                            ("against", "Crossing with the army was against the Republic."),
                        ),
                        flip_hints=(
                            "Who was with him, and who was supposed to be left behind?",
                            "Coming home from practice is not bringing the other team's bus into the hallway.",
                            "Home would be ____. This crossing was ____.",
                        ),
                        flip_trap=(
                            "road",
                            "Every road into Italy is legal for a general's army.",
                            "This boundary was the legal line.",
                        ),
                    ),
                    standard(
                        "ROM-U3-Q3",
                        "The Ides of March",
                        "core",
                        ["ROM-U3-Q2"],
                        ["generals"],
                        "Ask why killing Caesar did not automatically bring the Republic back.",
                        hook="On the Ides of March, senators killed Caesar. What problem were they trying to stop, and what problem did a killing not solve?",
                        hook_pair=(
                            ("stop", "They were trying to stop one man from standing above the laws."),
                            ("unsolved", "Killing him did not put the armies back under the laws."),
                        ),
                        hook_hints=(
                            "Can you stab a habit of soldiers following a person?",
                            "Ejecting the star player does not teach the team to listen to the referee.",
                            "They wanted to stop ____. The killing left ____.",
                        ),
                        hook_trap=(
                            "fixed",
                            "Removing the man restores every institution the same day.",
                            "The personal armies were still there.",
                        ),
                        toy_prompt="Why did the Ides of March fail to save the Republic by itself?",
                        choices=[
                            ("date", "March is a bad month for laws.", "The calendar is not the cause."),
                            ("armies", "Armies were still loyal to leaders, not repaired as institutions.", ""),
                            ("vote", "Plebeians had never wanted a republic.", "The Republic had lasted for centuries before this."),
                        ],
                        answer="armies",
                        toy_trap=(
                            "month",
                            "The date of the killing is the historical cause.",
                            "The cause that remained was loyalty and force.",
                        ),
                        gate="Why can a republic die even after the person who threatened it is gone?",
                        gate_pair=(
                            ("pattern", "The pattern was armies loyal to generals."),
                            ("person", "Removing one general leaves that pattern in place."),
                        ),
                        gate_hints=(
                            "Was Caesar the only person an army could love?",
                            "Taking down one captain does not delete the idea of a private team.",
                            "The pattern was ____. One death ____.",
                        ),
                        gate_trap=(
                            "name",
                            "Republics only fall because of one person's name.",
                            "The quest wants the structure under the name.",
                        ),
                        flip="Dagger Bot says the Republic was safe the moment Caesar fell. Teach the bot what was still broken.",
                        flip_pair=(
                            ("not-safe", "The killing did not make the Republic safe."),
                            ("loyalty", "Soldiers could still follow the next general."),
                        ),
                        flip_hints=(
                            "Who still had the armies the next morning?",
                            "The whistle is still missing even if the loudest player is gone.",
                            "Not safe because ____. The next danger was ____.",
                        ),
                        flip_trap=(
                            "done",
                            "A successful assassination is a successful reform.",
                            "Reform would have been putting force back under law.",
                        ),
                    ),
                    standard(
                        "ROM-U3-BOSS",
                        "Put Caesar on Trial",
                        "capstone",
                        ["ROM-U3-Q3"],
                        ["generals", "shared-power"],
                        "Ask your child to prosecute or defend Caesar using the army and the law, not a slogan.",
                        hook="You are speaking at Caesar's trial. Give one charge about the army and the law, and one thing a fair trial would still have to admit he did not invent alone.",
                        hook_pair=(
                            ("charge", "The charge is crossing into Italy with an army loyal to him, against the Republic."),
                            ("pattern", "The pattern of generals and personal armies was bigger than one man."),
                        ),
                        hook_hints=(
                            "A trial needs a specific act and the wider habit.",
                            "Blame the play and also the rule that let stars ignore the referee.",
                            "The charge is ____. The wider pattern is ____.",
                        ),
                        hook_trap=(
                            "slogan",
                            "Calling him a hero or a monster is a full case.",
                            "The capstone wants the army and the law.",
                        ),
                        toy_prompt="Which argument belongs at this trial?",
                        choices=[
                            ("birthday", "He should be convicted because of his birthday.", "A date is not the charge."),
                            ("rubicon", "He led an army across a legal line the Republic had drawn.", ""),
                            ("elephants", "He should be convicted for Hannibal's elephants.", "That war was generations earlier and not his act."),
                        ],
                        answer="rubicon",
                        toy_trap=(
                            "unrelated",
                            "Any famous Roman crime can be pinned on Caesar.",
                            "The trial is about his armed challenge to the Republic.",
                        ),
                        gate="How does this trial show that shared power collapses when force follows a person?",
                        gate_pair=(
                            ("force", "The soldiers followed Caesar rather than the Senate's limit."),
                            ("collapse", "Once force does that, the old checks cannot hold him inside the law."),
                        ),
                        gate_hints=(
                            "What were the soldiers obeying when they crossed?",
                            "If the team tackles the referee, the rulebook is no longer in charge.",
                            "They followed ____. The checks then ____.",
                        ),
                        gate_trap=(
                            "speech",
                            "The collapse happened because the Senate gave boring speeches.",
                            "The collapse in this quest is armed loyalty.",
                        ),
                        flip="Jury Bot says either Caesar was a perfect hero or the Senate was perfect. Teach a more precise verdict using the army and the laws.",
                        flip_pair=(
                            ("act", "Names the armed crossing as the act."),
                            ("system", "Names the wider failure of armies obeying generals."),
                        ),
                        flip_hints=(
                            "You can blame an act without pretending one man invented the whole disease.",
                            "A referee can call the foul and still admit the league let stars get too strong.",
                            "The act was ____. The system failed because ____.",
                        ),
                        flip_trap=(
                            "pure",
                            "A trial has to pick a pure hero.",
                            "This trial wants a precise cause.",
                        ),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                4,
                "Pax Romana, Engineering and The Empire Split",
                "Engineering united Rome, but overexpansion split it.",
                "Augustus sold peace after the civil wars, and roads, water, and concrete held distant cities together. The same reach that made the empire governable is what pulled it apart.",
                [
                    standard(
                        "ROM-U4-Q1",
                        "Augustus and Pax Romana",
                        "core",
                        ["ROM-U3-BOSS"],
                        ["empire"],
                        "Ask what kind of peace Augustus offered after the civil wars, and what power he kept.",
                        hook="After the civil wars, Augustus offered the Pax Romana, a long peace. What did people gain from that peace, and what power did he still keep?",
                        hook_pair=(
                            ("peace", "People gained an end to the civil-war fighting."),
                            ("power", "He kept the real control, including the armies, even without the title king."),
                        ),
                        hook_hints=(
                            "Peace from what, and who still commanded the soldiers?",
                            "A coach who stops the fight can still own the whistle.",
                            "People gained ____. Augustus kept ____.",
                        ),
                        hook_trap=(
                            "title",
                            "Refusing the word king means he had no special power.",
                            "The power was in the armies and the offices he stacked.",
                        ),
                        toy_prompt="What was the Pax Romana?",
                        choices=[
                            ("war", "A new civil war led by the Senate.", "It was a peace after the civil wars."),
                            ("peace", "A long peace under Augustus's control.", ""),
                            ("wall", "The wolf myth written on a wall.", "That is Unit 1's clue, not this peace."),
                        ],
                        answer="peace",
                        toy_trap=(
                            "senate-war",
                            "The Senate started a fresh civil war and called it peace.",
                            "The peace was the absence of that fighting, under his power.",
                        ),
                        gate="Why can a peace still be a warning if one person holds the armies that make the peace?",
                        gate_pair=(
                            ("quiet", "The fighting stopped, which was a real gain."),
                            ("warning", "The peace depended on the same personal control that had broken the Republic."),
                        ),
                        gate_hints=(
                            "Who can restart the war if they own the armies?",
                            "A quiet classroom is good, and it is fragile if one kid holds every hall pass.",
                            "The gain was ____. The warning was ____.",
                        ),
                        gate_trap=(
                            "only-good",
                            "Peace is always a full return to shared power.",
                            "This peace sat on top of concentrated power.",
                        ),
                        flip="Laurel Bot says Augustus brought the Republic back because the battles stopped. Teach the bot what kind of peace it was.",
                        flip_pair=(
                            ("stopped", "The civil battles did stop."),
                            ("held", "He held the power that had undone the old checks."),
                        ),
                        flip_hints=(
                            "Quiet streets are not the same as consuls who can veto a ruler.",
                            "No more fighting in the hallway, but one person still has the keys.",
                            "Battles ____. Power ____.",
                        ),
                        flip_trap=(
                            "restored",
                            "The end of fighting means the old offices are back in charge.",
                            "The offices were not the source of this peace.",
                        ),
                    ),
                    standard(
                        "ROM-U4-Q2A",
                        "Aqueducts and Concrete",
                        "branch",
                        ["ROM-U4-Q1"],
                        ["empire"],
                        "Ask how moving water and a new building material helped distant cities feel like one empire.",
                        hook="Aqueducts carried water to cities, and Roman concrete let them build harbors and huge vaults. How could those two inventions hold an empire together?",
                        hook_pair=(
                            ("water", "Aqueducts made big cities livable by bringing water."),
                            ("build", "Concrete let Rome build durable works that tied places together."),
                        ),
                        hook_hints=(
                            "What does a city need every day, and what lets you build a port that stays?",
                            "A water fountain at the field, and a bridge that does not wash away.",
                            "Water helps cities ____. Concrete helps Rome ____.",
                        ),
                        hook_trap=(
                            "pretty",
                            "The works mattered because they were pretty, not because they worked.",
                            "The quest is about use: water and durable building.",
                        ),
                        toy_prompt="What did an aqueduct do for a Roman city?",
                        choices=[
                            ("crown", "It chose the next emperor.", "It is engineering, not an election."),
                            ("water", "It carried water in from far away.", ""),
                            ("elephants", "It marched elephants over the Alps.", "That is Hannibal's war, not a water channel."),
                        ],
                        answer="water",
                        toy_trap=(
                            "politics",
                            "An aqueduct is a kind of senator.",
                            "It is a channel for water.",
                        ),
                        gate="Why is a shared building technique a political fact, not only a science fact, in an empire this large?",
                        gate_pair=(
                            ("same", "Cities could be built and supplied in a Roman way."),
                            ("link", "Those works linked distant people to the same system."),
                        ),
                        gate_hints=(
                            "Who do you depend on if your water arrives on their arches?",
                            "If every playground uses the same pipes, the playgrounds are one network.",
                            "The technique made cities ____. That linked them because ____.",
                        ),
                        gate_trap=(
                            "only-lab",
                            "Concrete is only a lab trick with no effect on who governs.",
                            "Infrastructure is how a government shows up in daily life.",
                        ),
                        flip="Dust Bot says aqueducts and concrete are just messy work, unrelated to Rome's power. Teach the bot how they united the empire.",
                        flip_pair=(
                            ("supply", "Water and durable buildings supplied city life."),
                            ("unite", "That supply united distant places under one system."),
                        ),
                        flip_hints=(
                            "What breaks in a city if the arches fail?",
                            "Shared pipes are a kind of membership.",
                            "They supplied ____ and united ____.",
                        ),
                        flip_trap=(
                            "mud",
                            "Building is the opposite of politics.",
                            "This building was the politics you could drink and walk on.",
                        ),
                    ),
                    standard(
                        "ROM-U4-Q2B",
                        "Pompeii and the Colosseum",
                        "branch",
                        ["ROM-U4-Q1"],
                        ["empire"],
                        "Ask what a buried city and a giant arena show about ordinary life under the empire.",
                        hook="Pompeii was buried with its streets, shops, and graffiti still in place. The Colosseum held huge crowds. What can a city frozen in ash show, and what can a giant arena show?",
                        hook_pair=(
                            ("daily", "Pompeii shows daily life, not only kings and battles."),
                            ("crowd", "The Colosseum shows a government that could gather and impress huge crowds."),
                        ),
                        hook_hints=(
                            "One source is a neighborhood. The other is a show for thousands.",
                            "A time capsule of a street, and a stadium built to fill.",
                            "Ash shows ____. The arena shows ____.",
                        ),
                        hook_trap=(
                            "kings-only",
                            "The only history that counts is what emperors wrote.",
                            "This branch uses places ordinary people stood.",
                        ),
                        toy_prompt="Why is Pompeii a special clue?",
                        choices=[
                            ("myth", "It proves the wolf myth word for word.", "The wolf story is not what the ash preserved."),
                            ("ash", "Ash kept a city's ordinary streets and objects.", ""),
                            ("vote", "It is where Rome voted out Tarquin.", "That vote was centuries earlier in Rome."),
                        ],
                        answer="ash",
                        toy_trap=(
                            "myth-proof",
                            "Every ruin proves the founding myth.",
                            "Pompeii is evidence of imperial daily life.",
                        ),
                        gate="How do a preserved town and a public arena together tell you the empire was more than a list of rulers?",
                        gate_pair=(
                            ("people", "People lived, shopped, and wrote on walls inside the empire."),
                            ("spectacle", "The state spent huge effort on shared public shows."),
                        ),
                        gate_hints=(
                            "What would be missing if we only had the emperor's name?",
                            "A diary of a street plus the school assembly.",
                            "The town shows ____. The arena shows ____.",
                        ),
                        gate_trap=(
                            "list",
                            "Names of rulers already include daily life.",
                            "Names do not show a shop or a crowd.",
                        ),
                        flip="Scroll Bot says history is only the emperor's letters. Teach the bot using Pompeii and the Colosseum.",
                        flip_pair=(
                            ("pompeii", "Uses Pompeii as evidence of ordinary life."),
                            ("arena", "Uses the Colosseum as evidence of public spectacle."),
                        ),
                        flip_hints=(
                            "Put one object from the street and one fact about the crowd in the lesson.",
                            "A lunch counter and a stadium are both evidence.",
                            "Pompeii shows ____. The Colosseum shows ____.",
                        ),
                        flip_trap=(
                            "letters",
                            "If it was not written by an emperor, it is not evidence.",
                            "Places are evidence.",
                        ),
                    ),
                    standard(
                        "ROM-U4-BOSS",
                        "Why Rome Split",
                        "capstone",
                        ["ROM-U4-Q2A", "ROM-U4-Q2B"],
                        ["empire"],
                        "Ask why an empire that could move water and fill arenas could still split.",
                        hook="The empire could build across a huge map, and it still split. What is one way that size and engineering held it together, and one way the same size pulled it apart?",
                        hook_pair=(
                            ("held", "Roads, water, concrete, and shared public life held distant cities in one system."),
                            ("split", "The same huge reach was too much to govern as one, so it split."),
                        ),
                        hook_hints=(
                            "Use both branches: something built, and the problem of distance.",
                            "A giant group chat keeps friends in touch and also becomes impossible to manage.",
                            "It held together by ____. It split because ____.",
                        ),
                        hook_trap=(
                            "only-build",
                            "Engineering success means a state cannot split.",
                            "The capstone is that the success and the split share a cause: size.",
                        ),
                        toy_prompt="Which explanation of the split uses this unit?",
                        choices=[
                            ("wolf", "The wolf myth stopped being popular.", "The myth is not why the later empire split."),
                            ("reach", "The empire's huge reach, which engineering had helped unite, became too large to govern as one.", ""),
                            ("gold", "Rome ran out of gold coins in a single afternoon.", "A one-day cash story is not the unit's cause."),
                        ],
                        answer="reach",
                        toy_trap=(
                            "cash",
                            "Empires split only because the treasury hits zero in a day.",
                            "This unit's cause is overexpansion.",
                        ),
                        gate="Using aqueducts or concrete and the problem of distance, explain why engineering united Rome and overexpansion split it.",
                        gate_pair=(
                            ("unite", "Explains a built system that united distant cities."),
                            ("over", "Explains that the same expansion became too large to hold as one government."),
                        ),
                        gate_hints=(
                            "Name a work from the branch quests, then name the cost of the map.",
                            "The pipes that connect the houses also show how far apart the houses are.",
                            "United by ____. Split by ____.",
                        ),
                        gate_trap=(
                            "barbarian-only",
                            "The only allowed cause is a single enemy at the gate, with no role for size.",
                            "The quest's cause is overexpansion of a system that had been a strength.",
                        ),
                        flip="Border Bot says Rome split because concrete was a bad invention. Teach the bot the real pair: engineering united it, overexpansion split it.",
                        flip_pair=(
                            ("not-bad", "Concrete and aqueducts were a strength, not the failure."),
                            ("size", "The split came from a reach that governing could not hold."),
                        ),
                        flip_hints=(
                            "Do not let the bot blame the tool for the size of the job.",
                            "A great bridge is not why the continent is wide.",
                            "The inventions ____. The split came from ____.",
                        ),
                        flip_trap=(
                            "tool",
                            "If a state ends, its tools must have been mistakes.",
                            "The tools did their job. The map outgrew one government.",
                        ),
                        flip_bloom="create",
                    ),
                ],
            ),
        ],
    )

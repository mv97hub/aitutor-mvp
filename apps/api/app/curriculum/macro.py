"""AP Macroeconomics, ages 15–17. Quest codes match the blueprint."""

from app.curriculum.shape import course, flaw, ladder, quest, rubric, standard, traps, unit

COMPETENCIES = [
    ("indicators", "Separate nominal prices from real GDP, unemployment types, and the CPI."),
    ("ad-as", "A short-run gap closes when SRAS shifts or fiscal policy shifts AD."),
    ("money", "Interest rates clear loanable funds and reserves. The Fed steers the policy rate."),
    ("phillips", "A demand shock moves along the SRPC. A supply shock shifts it."),
    ("forex", "Interest rates move capital flows, the exchange rate, and net exports."),
]


def _central_banker() -> dict:
    """MAC-U4-Q1 written beats, including the flawed FOMC memo."""
    beats = [
        {
            "role": "mystery_hook",
            "bloom_level": "analyze",
            "cognitive_load": "high",
            "prompt": (
                "Inflation is 6.5 percent from a positive AD shock (Y greater than Yf). "
                "Trace the causal chain when the Fed raises interest rates."
            ),
            "rubric": rubric(
                (
                    "borrowing",
                    "Higher rates raise borrowing costs, reducing investment and interest-sensitive consumption.",
                    35,
                ),
                ("ad", "AD shifts left, lowering the price level and real GDP.", 35),
                (
                    "unemployment",
                    "Lower real GDP raises short-run cyclical unemployment.",
                    30,
                ),
            ),
            "misconception_map": traps(
                (
                    "price-only",
                    "Higher rates lower inflation without touching output or jobs.",
                    "The same leftward AD shift lowers real GDP and raises cyclical unemployment.",
                )
            ),
            "hint_ladder": ladder(
                "Which spending is sensitive to the price of a loan?",
                "A more expensive loan is a gate on a factory and on a financed purchase.",
                "Higher rates cut ____, AD shifts ____, and cyclical unemployment ____.",
            ),
            "widget": None,
        },
        {
            "role": "interactive_toy",
            "bloom_level": "understand",
            "cognitive_load": "medium",
            "prompt": (
                "An oil or supply shock shifts SRAS left (stagflation). "
                "How does this appear on the short-run Phillips curve?"
            ),
            "rubric": rubric(
                (
                    "shift",
                    "The entire SRPC shifts outward or right because inflation and unemployment worsen together.",
                    100,
                )
            ),
            "misconception_map": traps(
                (
                    "along",
                    "Stagflation is a move along a fixed short-run Phillips curve.",
                    "A move along the curve is a demand shock. A supply shock shifts the curve.",
                ),
                (
                    "lrpc-up",
                    "The long-run Phillips curve slopes upward, and that is the stagflation picture.",
                    "The long-run curve is vertical. Stagflation is a short-run shift.",
                ),
            ),
            "hint_ladder": ladder(
                "Does a supply shock pick a new point on the old curve, or move the whole curve?",
                "A demand shock slides you along the menu. A supply shock reprints the menu.",
                "Both inflation and unemployment worsen together, so the SRPC shifts ____.",
            ),
            "widget": {
                "type": "single",
                "prompt": "An oil or supply shock shifts SRAS left. How does this appear on the short-run Phillips curve?",
                "choices": [
                    {
                        "id": "along",
                        "text": "Moves up and left along a fixed SRPC.",
                        "misconception": "That is the AD trap. A move along a fixed SRPC is a demand shock.",
                    },
                    {
                        "id": "upward",
                        "text": "The LRPC slopes upward.",
                        "misconception": "The long-run Phillips curve is vertical, not an upward stagflation path.",
                    },
                    {
                        "id": "shift",
                        "text": "The entire SRPC shifts outward or right because both inflation and unemployment worsen at once.",
                        "misconception": "",
                    },
                ],
                "answer": "shift",
                "explain": False,
                "misconception": "A supply shock moves the curve. A demand shock moves along it.",
            },
        },
        {
            "role": "diagnostic_gate",
            "bloom_level": "evaluate",
            "cognitive_load": "high",
            "prompt": (
                "Read the four-sentence FOMC memo. Segment 3 claims that cutting interest rates to shift AD right "
                "will simultaneously cure inflation and restore full employment during stagflation. "
                "Flag the flawed segment and explain the catch-22."
            ),
            "rubric": rubric(
                ("segment", "Flags segment 3.", 40),
                (
                    "catch22",
                    "Monetary policy only shifts AD, so AD right saves jobs but worsens inflation, and AD left fights inflation but deepens unemployment.",
                    60,
                ),
            ),
            "misconception_map": traps(
                (
                    "both-goals",
                    "One AD shift can hit a lower inflation rate and a lower unemployment rate during stagflation.",
                    "Those two goals sit on opposite AD moves when the problem is SRAS.",
                )
            ),
            "hint_ladder": ladder(
                "Which sentence promises both goals from one shift of AD?",
                "A single lever on aggregate demand cannot push inflation and unemployment down together after a supply shock.",
                "Policy only shifts ____, so one direction ____ and the other direction ____.",
            ),
            "widget": flaw(
                "Which segment of the FOMC memo has the policy flaw?",
                [
                    (
                        "s1",
                        "Inflation and unemployment are both high after a supply shock.",
                        "That sentence only names stagflation. It is not the policy error.",
                    ),
                    (
                        "s2",
                        "The short-run Phillips curve has shifted, so the old tradeoff no longer sits on the same line.",
                        "That sentence describes the shift. It is not the policy error.",
                    ),
                    (
                        "s3",
                        "Cutting interest rates to shift AD right will simultaneously cure inflation and restore full employment.",
                        "Monetary policy only shifts AD. AD right saves jobs and worsens inflation. AD left does the opposite.",
                    ),
                    (
                        "s4",
                        "The committee should name which goal it will miss if it moves aggregate demand.",
                        "That sentence asks for the tradeoff. It is not the flaw.",
                    ),
                ],
                "s3",
                explain=True,
                misconception="Find the sentence that promises both goals from one move of AD.",
            ),
        },
        {
            "role": "feynman_flip",
            "bloom_level": "evaluate",
            "cognitive_load": "high",
            "prompt": (
                "Rebut Cable Pundit Bot during a recessionary gap with 8 percent unemployment. "
                "The bot claims workers will demand huge wage raises and the Fed should raise rates. "
                "Contrast long-run self-adjustment (high unemployment causes nominal wages to fall, SRAS shifts right) "
                "with active Fed policy (cutting rates shifts AD right)."
            ),
            "rubric": rubric(
                (
                    "wages",
                    "High unemployment causes nominal wages to fall, so SRAS shifts right.",
                    50,
                ),
                (
                    "cut",
                    "Active Fed policy in this gap cuts rates and shifts AD right.",
                    50,
                ),
            ),
            "misconception_map": traps(
                (
                    "raise-in-slump",
                    "High unemployment makes workers demand huge raises, so the Fed should hike.",
                    "A recessionary gap puts downward pressure on nominal wages. A hike would shift AD further left.",
                )
            ),
            "hint_ladder": ladder(
                "In a slump, are workers in a position to demand a huge raise, or are jobs scarce?",
                "A long line of applicants is pressure down on the wage, not up.",
                "Self-adjustment: wages ____ and SRAS shifts ____. Active policy: the Fed ____ rates and AD shifts ____.",
            ),
            "widget": None,
        },
    ]
    return quest(
        "MAC-U4-Q1",
        "The Central Banker's Dilemma: Monetary Transmission and Stagflation",
        "core",
        ["MAC-U3-BOSS"],
        ["phillips", "money"],
        "At dinner, ask why a central bank cannot cure stagflation by moving aggregate demand in one direction.",
        beats,
    )


def macro_course() -> dict:
    return course(
        "macro",
        "AP Macroeconomics: National Output, Central Banking and Stabilization Policy",
        "15-17",
        "College Board AP Macro",
        COMPETENCIES,
        [
            unit(
                1,
                "Scarcity, Comparative Advantage and Macro Indicators",
                "Separate nominal price illusions from real GDP, unemployment types, and CPI.",
                "Nominal prices can rise while real output does not, and not every jobless person is in the same kind of unemployment. Those measures are what the next unit's gaps are measured against.",
                [
                    standard(
                        "MAC-U1-Q1",
                        "PPC and Trade",
                        "core",
                        [],
                        ["indicators"],
                        "Ask what a point outside the PPC means, and why trade can rest on comparative advantage.",
                        hook="A country can make drones or wheat. A point outside the PPC is wanted and impossible in the short run. What does a bowed-out PPC say about opportunity cost, and how can trade still raise consumption?",
                        hook_pair=(
                            ("cost", "Moving along the PPC raises the opportunity cost of the good you expand."),
                            ("trade", "Comparative advantage lets each side export the good with the lower opportunity cost and consume beyond one country's PPC."),
                        ),
                        hook_hints=(
                            "What do you give up as you slide toward one axis?",
                            "Two kitchens, each faster at a different dish, trading plates.",
                            "Opportunity cost ____ as you specialize. Trade can raise consumption because ____.",
                        ),
                        hook_trap=("outside-now", "A point outside the PPC is a normal production plan for this year.", "It is unattainable with current resources."),
                        toy_prompt="Which statement about comparative advantage is right?",
                        choices=[
                            ("absolute", "Trade only helps the country that is absolutely better at both goods.", "Comparative advantage can hold for the country that is worse at both."),
                            ("opportunity", "A country exports the good with the lower opportunity cost.", ""),
                            ("outside", "Trade is useful only to reach a point inside the PPC.", "The gain is consumption beyond the single-country PPC."),
                        ],
                        answer="opportunity",
                        toy_trap=("absolute-only", "Absolute advantage is the only reason to trade.", "The reason to trade is a lower opportunity cost."),
                        gate="Why can two countries both consume outside their own PPCs after trade even though neither can produce outside its PPC?",
                        gate_pair=(
                            ("produce", "Production stays on or inside each PPC."),
                            ("consume", "Consumption can sit outside a country's PPC because the other country produces the costly good."),
                        ),
                        gate_hints=(
                            "Separate the production point from the consumption point.",
                            "You still cook on your own stove. You eat from both kitchens.",
                            "Production cannot ____. Consumption can ____.",
                        ),
                        gate_trap=("produce-outside", "Trade moves the PPC out immediately.", "The PPC is resources and technology. Trade changes the consumption mix."),
                        flip="Closed Bot says a country that is worse at every good should not trade. Teach comparative advantage.",
                        flip_pair=(
                            ("lower", "Export the good with the lower opportunity cost."),
                            ("both", "Both sides can consume more than they could alone."),
                        ),
                        flip_hints=(
                            "Ask the bot about what you give up, not about who is faster in absolute hours.",
                            "The slower cook can still be the cheaper salad.",
                            "Compare ____. Then both can ____.",
                        ),
                        flip_trap=("autarky", "Being worse at everything means there is no gain from trade.", "Opportunity cost can still differ."),
                    ),
                    standard(
                        "MAC-U1-Q2",
                        "Nominal vs Real GDP",
                        "core",
                        ["MAC-U1-Q1"],
                        ["indicators"],
                        "Ask how a price rise can inflate nominal GDP while real output stands still.",
                        hook="Nominal GDP uses this year's prices. Real GDP uses a base year's prices. If every price doubles and every quantity stays put, what happens to each measure?",
                        hook_pair=(
                            ("nominal", "Nominal GDP doubles because it is priced in the new dollars."),
                            ("real", "Real GDP stays put because quantities did not change."),
                        ),
                        hook_hints=(
                            "Which measure is allowed to notice the new price tags?",
                            "The receipt total versus the number of boxes.",
                            "Nominal GDP ____. Real GDP ____.",
                        ),
                        hook_trap=("both-double", "Real GDP doubles whenever nominal GDP doubles.", "Real GDP holds prices fixed."),
                        toy_prompt="Prices rise and quantities do not. Which measure rises?",
                        choices=[
                            ("real", "Real GDP only.", "Real GDP is holding the old prices."),
                            ("nominal", "Nominal GDP, not real GDP.", ""),
                            ("neither", "Neither, because people buy the same basket.", "The same basket at higher prices still raises the nominal total."),
                        ],
                        answer="nominal",
                        toy_trap=("basket", "An unchanged basket keeps nominal GDP unchanged.", "Nominal GDP multiplies by the new prices."),
                        gate="Why is a nominal GDP record a bad way to claim the country produced more?",
                        gate_pair=(
                            ("mix", "Nominal GDP mixes prices and quantities."),
                            ("real-needed", "A production claim needs real GDP, or nominal GDP deflated by a price index."),
                        ),
                        gate_hints=(
                            "Name the two things multiplied inside nominal GDP.",
                            "A bigger dinner check can be inflation or more food.",
                            "Nominal mixes ____. Production needs ____.",
                        ),
                        gate_trap=("receipt", "A bigger receipt is always more output.", "The receipt includes prices."),
                        flip="Receipt Bot celebrates a nominal GDP jump as a production boom. Separate the price illusion from real output.",
                        flip_pair=(
                            ("illusion", "The jump may be prices."),
                            ("check", "Real GDP, or a deflator, is the check on quantities."),
                        ),
                        flip_hints=(
                            "Ask the bot what happened to the boxes, not the stickers.",
                            "Deflate the receipt.",
                            "The illusion is ____. The check is ____.",
                        ),
                        flip_trap=("always-real", "Nominal and real move together by definition.", "They move together only when prices are stable."),
                    ),
                    standard(
                        "MAC-U1-Q3",
                        "Frictional, Structural and Cyclical Unemployment",
                        "core",
                        ["MAC-U1-Q2"],
                        ["indicators"],
                        "Ask which kind of unemployment a recession creates, and which kinds exist at full employment.",
                        hook="A worker is between jobs, a skill has become obsolete, and a factory idles in a recession. Which unemployment is which?",
                        hook_pair=(
                            ("types", "Frictional is the search between jobs. Structural is the obsolete skill. Cyclical is the recession idle."),
                            ("full", "Frictional and structural remain at full employment. Cyclical does not."),
                        ),
                        hook_hints=(
                            "Which one disappears when the economy is at potential?",
                            "A short job hunt, a vanished trade, and a slump.",
                            "Frictional is ____. Structural is ____. Cyclical is ____.",
                        ),
                        hook_trap=("all-cyclical", "Every jobless person is a recession statistic.", "Search and mismatch exist at the natural rate."),
                        toy_prompt="A coder's language is no longer used, and the economy is at potential. What unemployment is that?",
                        choices=[
                            ("cyclical", "Cyclical.", "Potential output means the recession gap is not the cause."),
                            ("structural", "Structural.", ""),
                            ("frictional", "Frictional, because any job search is short by definition.", "A vanished skill is a mismatch, not a brief search."),
                        ],
                        answer="structural",
                        toy_trap=("search", "All unemployment that involves looking for work is frictional.", "The cause of the search matters."),
                        gate="Why can the natural rate of unemployment be positive while cyclical unemployment is zero?",
                        gate_pair=(
                            ("natural", "The natural rate includes frictional and structural unemployment."),
                            ("zero-cyclical", "Cyclical unemployment is the extra joblessness of a downturn, so it is zero at potential."),
                        ),
                        gate_hints=(
                            "Full employment is not zero unemployment.",
                            "A healthy labor market still has people walking between desks and people whose desks vanished.",
                            "Natural includes ____. Cyclical is zero when ____.",
                        ),
                        gate_trap=("zero", "Full employment means nobody is jobless.", "It means no cyclical unemployment."),
                        flip="Headline Bot calls every unemployment rate a recession. Sort the three types for the bot.",
                        flip_pair=(
                            ("sort", "Separates frictional, structural, and cyclical."),
                            ("recession", "Only cyclical unemployment is the recession's addition."),
                        ),
                        flip_hints=(
                            "Give the bot one person for each type.",
                            "Three causes, one headline.",
                            "Frictional ____. Structural ____. Cyclical ____.",
                        ),
                        flip_trap=("one-cause", "Unemployment has one cause, so the rate is the business cycle.", "The rate is a sum of causes."),
                    ),
                    standard(
                        "MAC-U1-BOSS",
                        "Diagnose the Business Cycle",
                        "capstone",
                        ["MAC-U1-Q3"],
                        ["indicators"],
                        "Ask your child to tell a real contraction from a nominal scare using output, jobs, and prices.",
                        hook="Real GDP is falling, cyclical unemployment is rising, and the CPI is flat. Diagnose the phase. What would a rising CPI with flat real GDP have meant instead?",
                        hook_pair=(
                            ("contraction", "Falling real GDP and rising cyclical unemployment is a contraction."),
                            ("nominal", "A rising CPI with flat real GDP would be a nominal price rise, not a real boom or a real contraction."),
                        ),
                        hook_hints=(
                            "Which two facts are about quantities and jobs, and which fact is a price tag?",
                            "Fewer boxes and more layoffs, versus stickers changing on the same boxes.",
                            "This case is a ____. The other case would be ____.",
                        ),
                        hook_trap=("cpi-contraction", "Any CPI move is a contraction.", "The contraction signal here is real GDP and cyclical jobs."),
                        toy_prompt="Which pair diagnoses a real contraction?",
                        choices=[
                            ("prices", "CPI up, real GDP unchanged.", "That is a price change without a quantity drop."),
                            ("output", "Real GDP down, cyclical unemployment up.", ""),
                            ("friction", "Frictional unemployment up, real GDP at potential.", "That can be ordinary search at full employment."),
                        ],
                        answer="output",
                        toy_trap=("price-cycle", "The business cycle is read off the CPI alone.", "The cycle is real output and cyclical unemployment."),
                        gate="Why must a cycle diagnosis use real GDP and the type of unemployment, not the nominal level of spending?",
                        gate_pair=(
                            ("real", "Real GDP tells you whether quantities fell."),
                            ("type", "Only cyclical unemployment says the job loss is the downturn rather than search or mismatch."),
                        ),
                        gate_hints=(
                            "A spending total can rise because of prices.",
                            "Separate the receipt from the layoffs that came from a demand slump.",
                            "Real GDP is needed because ____. Unemployment type is needed because ____.",
                        ),
                        gate_trap=("spending", "Nominal spending is the business cycle.", "Nominal spending mixes prices in."),
                        flip="Dashboard Bot sees a higher CPI and announces a boom. Rebuild the diagnosis with this unit's indicators.",
                        flip_pair=(
                            ("not-boom", "A higher CPI is not by itself a real boom."),
                            ("use", "A real diagnosis uses real GDP and cyclical unemployment."),
                        ),
                        flip_hints=(
                            "Take the price sticker off the dashboard.",
                            "Ask what happened to boxes and to recession layoffs.",
                            "CPI does not prove ____. Look at ____.",
                        ),
                        flip_trap=("sticker-boom", "Higher prices mean the country produced a boom.", "Higher prices can hide flat output."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                2,
                "AD-AS, Fiscal Multipliers and Self-Adjustment",
                "Short-run gaps close via sticky-to-flexible nominal wages shifting SRAS, or fiscal policy shifting AD.",
                "Aggregate demand and short-run aggregate supply are the curves that move when spending or costs change. A gap can close because wages adjust and SRAS shifts, or because fiscal policy shifts AD.",
                [
                    standard(
                        "MAC-U2-Q1",
                        "Aggregate Demand and Multipliers",
                        "core",
                        ["MAC-U1-BOSS"],
                        ["ad-as"],
                        "Ask why one dollar of new spending can raise equilibrium GDP by more than a dollar.",
                        hook="The government buys one extra dollar of goods. Households spend part of each new dollar of income. Why is the rise in equilibrium real GDP larger than the first dollar, and what limits the multiplier?",
                        hook_pair=(
                            ("rounds", "Each round of induced consumption adds more spending, so the total exceeds the first dollar."),
                            ("leak", "Saving, taxes, and imports leak out of each round and keep the multiplier finite."),
                        ),
                        hook_hints=(
                            "What does the next household do with the income the first purchase created?",
                            "A dollar that is partly respent down a line of shops, with some money leaving the line.",
                            "The total is larger because ____. It is finite because ____.",
                        ),
                        hook_trap=("one-for-one", "GDP rises by exactly the first dollar and then stops.", "Induced consumption continues the chain."),
                        toy_prompt="What makes a spending multiplier larger?",
                        choices=[
                            ("save-more", "Households save a larger share of extra income.", "A larger save leak shrinks the multiplier."),
                            ("consume-more", "Households spend a larger share of extra income.", ""),
                            ("imports", "Every extra dollar is spent on imports.", "Imports are a leak. They shrink the domestic multiplier."),
                        ],
                        answer="consume-more",
                        toy_trap=("leak-larger", "Bigger leaks raise the multiplier.", "Leaks shrink it."),
                        gate="Why does the multiplier shift AD by more than the initial government purchase, rather than sliding along a fixed AD curve?",
                        gate_pair=(
                            ("shift", "The extra rounds are new spending, so AD shifts right by the multiplied amount."),
                            ("not-slide", "A slide along AD would be a price change, not a new injection of spending."),
                        ),
                        gate_hints=(
                            "Is the second round a higher price or another purchase?",
                            "New orders shift the demand curve. A price tick moves you along it.",
                            "AD shifts because ____. A slide would be ____.",
                        ),
                        gate_trap=("along", "Fiscal spending moves the economy along AD.", "It shifts AD."),
                        flip="One-Dollar Bot says GDP rises by the government purchase and no more. Teach the induced rounds and one leak.",
                        flip_pair=(
                            ("induced", "Later households spend part of the new income."),
                            ("leak", "A leak such as saving stops the chain from being infinite."),
                        ),
                        flip_hints=(
                            "Follow the income into the next shop.",
                            "Then show the money that never gets respent.",
                            "Induced spending ____. A leak ____.",
                        ),
                        flip_trap=("exact", "Equilibrium output equals the initial injection.", "The multiplier says otherwise."),
                    ),
                    standard(
                        "MAC-U2-Q2",
                        "SRAS vs LRAS",
                        "core",
                        ["MAC-U2-Q1"],
                        ["ad-as"],
                        "Ask why firms can produce beyond potential for a while, and why they cannot stay there.",
                        hook="SRAS slopes up. LRAS is vertical at potential output Yf. Why can an economy sit to the right of LRAS in the short run, and why is that not a long-run equilibrium?",
                        hook_pair=(
                            ("sticky", "Sticky nominal wages and prices let firms supply more when the price level rises before costs catch up."),
                            ("not-long", "Once nominal wages adjust, SRAS shifts and output returns to Yf."),
                        ),
                        hook_hints=(
                            "What has not risen yet when the price of output rises?",
                            "A short overtime shift before the contract is renegotiated.",
                            "Short run works because ____. It is not long-run because ____.",
                        ),
                        hook_trap=("stay", "An economy can sit beyond Yf forever if demand stays high.", "Wages catch up and SRAS moves."),
                        toy_prompt="What does a vertical LRAS mean?",
                        choices=[
                            ("prices-fixed", "The price level is fixed in the long run.", "The long-run curve is about output, not a fixed price."),
                            ("potential", "Long-run output is potential output, independent of the price level.", ""),
                            ("always-short", "The economy is always on SRAS and LRAS at once, even in a gap.", "A gap is on SRAS and off LRAS."),
                        ],
                        answer="potential",
                        toy_trap=("fixed-price", "Long run means prices cannot change.", "Long run means output is back at potential after prices and wages adjust."),
                        gate="How do sticky nominal wages explain the upward slope of SRAS?",
                        gate_pair=(
                            ("profit", "A higher price level with a sticky wage raises the real profit on extra output."),
                            ("slope", "Firms therefore supply more real GDP as the price level rises, which is the upward slope."),
                        ),
                        gate_hints=(
                            "Hold the wage still and raise the price of the product.",
                            "The contract is last year's number. The sticker on the product is new.",
                            "Profit rises because ____. So the curve slopes ____.",
                        ),
                        gate_trap=("flexible-now", "SRAS slopes up because wages are fully flexible immediately.", "Flexibility is the long-run adjustment, not the short-run slope."),
                        flip="Vertical Bot draws SRAS as a vertical line at Yf. Correct the time horizon.",
                        flip_pair=(
                            ("sras", "SRAS slopes up because wages are sticky."),
                            ("lras", "LRAS is the vertical line at potential, after wages adjust."),
                        ),
                        flip_hints=(
                            "Ask the bot which curve is allowed to be off potential.",
                            "Overtime now, renegotiation later.",
                            "SRAS ____. LRAS ____.",
                        ),
                        flip_trap=("one-curve", "There is only one aggregate supply curve.", "The horizon splits them."),
                    ),
                    standard(
                        "MAC-U2-Q3",
                        "Long-Run Self-Adjustment",
                        "core",
                        ["MAC-U2-Q2"],
                        ["ad-as"],
                        "Ask which way nominal wages move in a recessionary gap, and which way SRAS shifts.",
                        hook="A recessionary gap has unemployment above the natural rate. With no fiscal or monetary action, which way do nominal wages move, and which way does SRAS shift?",
                        hook_pair=(
                            ("wages", "High unemployment puts downward pressure on nominal wages."),
                            ("sras", "Lower nominal wages shift SRAS to the right, back toward Yf."),
                        ),
                        hook_hints=(
                            "Are workers scarce or plentiful in this gap?",
                            "A long hiring line bargains wages down, and cheaper labor shifts supply right.",
                            "Wages ____. SRAS shifts ____.",
                        ),
                        hook_trap=("raises", "A recession makes workers demand huge wage increases.", "Job scarcity pushes wages down, not up."),
                        toy_prompt="In a recessionary gap, self-adjustment moves which curve?",
                        choices=[
                            ("ad-right", "AD shifts right as wages rise.", "Wages are not rising, and the self-adjustment is on SRAS."),
                            ("sras-right", "SRAS shifts right as nominal wages fall.", ""),
                            ("lras-left", "LRAS shifts left to the low output.", "Potential does not chase the slump. SRAS moves toward potential."),
                        ],
                        answer="sras-right",
                        toy_trap=("move-potential", "The long-run curve moves to wherever output happens to be.", "Self-adjustment returns output to the existing Yf."),
                        gate="Contrast the wage move in an inflationary gap with the wage move in a recessionary gap.",
                        gate_pair=(
                            ("inflationary", "In an inflationary gap, tight labor pushes nominal wages up and SRAS shifts left."),
                            ("recessionary", "In a recessionary gap, slack labor pushes nominal wages down and SRAS shifts right."),
                        ),
                        gate_hints=(
                            "Which gap has scarce workers?",
                            "Overtime premiums versus a long unemployment line.",
                            "Inflationary gap: wages ____ and SRAS ____. Recessionary gap: wages ____ and SRAS ____.",
                        ),
                        gate_trap=("same-way", "Wages always rise after a gap, whichever side of Yf you are on.", "The sign follows the labor market."),
                        flip="Pundit Bot says a recessionary gap self-corrects by workers demanding raises. Replace that story.",
                        flip_pair=(
                            ("down", "Nominal wages fall when unemployment is high."),
                            ("right", "SRAS shifts right until output returns to Yf."),
                        ),
                        flip_hints=(
                            "Who has the bargaining power in a slump?",
                            "The line of applicants, not a shortage of applicants.",
                            "Wages ____. SRAS ____.",
                        ),
                        flip_trap=("raise-sras-left", "Self-correction in a slump is an SRAS shift left.", "Left would deepen the gap."),
                    ),
                    standard(
                        "MAC-U2-BOSS",
                        "Close an Output Gap with Multipliers",
                        "capstone",
                        ["MAC-U2-Q3"],
                        ["ad-as"],
                        "Ask how big a fiscal shift has to be once you know the multiplier and the size of the gap.",
                        hook="Real GDP is $50 billion below Yf and the spending multiplier is 2. What initial change in government spending closes the gap, and which curve moves?",
                        hook_pair=(
                            ("size", "The initial spending change is the gap divided by the multiplier, so $25 billion."),
                            ("ad", "That spending shifts AD right until short-run output meets Yf."),
                        ),
                        hook_hints=(
                            "If each first dollar becomes two, how many first dollars make fifty?",
                            "You do not inject the whole gap. You inject the gap divided by the multiplier.",
                            "Spend ____. AD shifts ____.",
                        ),
                        hook_trap=("inject-gap", "Close a $50 billion gap with $50 billion of spending when the multiplier is 2.", "That would overshoot."),
                        toy_prompt="The gap is $50 billion and the multiplier is 2. How much new government spending closes it?",
                        choices=[
                            ("fifty", "$50 billion.", "That ignores the induced rounds and overshoots."),
                            ("twenty-five", "$25 billion.", ""),
                            ("hundred", "$100 billion.", "That multiplies the gap again instead of dividing."),
                        ],
                        answer="twenty-five",
                        toy_trap=("overshoot", "The injection should equal the gap.", "The injection should equal the gap divided by the multiplier."),
                        gate="Why can this fiscal close of a recessionary gap arrive before wage-driven self-adjustment, and what is the different curve?",
                        gate_pair=(
                            ("faster", "Fiscal policy can shift AD now, while nominal wages are still sticky."),
                            ("curve", "Fiscal policy shifts AD. Self-adjustment shifts SRAS."),
                        ),
                        gate_hints=(
                            "Which curve did Unit 2's self-adjustment move?",
                            "A new order book versus a slower wage renegotiation.",
                            "Fiscal can be faster because ____. It moves ____, while self-adjustment moves ____.",
                        ),
                        gate_trap=("same-curve", "Fiscal policy and self-adjustment shift the same curve.", "One shifts AD. The other shifts SRAS."),
                        flip="Budget Bot wants to spend the entire gap and also calls that an SRAS policy. Correct the size and the curve.",
                        flip_pair=(
                            ("divide", "Spend the gap divided by the multiplier."),
                            ("ad-not-sras", "The policy shifts AD, not SRAS."),
                        ),
                        flip_hints=(
                            "Hand the bot the division, then the curve name.",
                            "Half the gap in first dollars, landing on the demand curve.",
                            "The size is ____. The curve is ____.",
                        ),
                        flip_trap=("whole-sras", "Spending the whole gap shifts SRAS right by the gap.", "Spending shifts AD, and the multiplier means you spend less than the gap."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                3,
                "Financial Markets, Banking and the Federal Reserve",
                "Interest rates equilibrate loanable funds and reserves. The Fed steers rates via administered rates or open-market operations.",
                "The policy rate is the price the Fed is steering, through reserves and administered rates. Loanable funds and bank T-accounts are how that rate reaches borrowers.",
                [
                    standard(
                        "MAC-U3-Q1",
                        "Fisher Effect and Loanable Funds",
                        "core",
                        ["MAC-U2-BOSS"],
                        ["money"],
                        "Ask how expected inflation gets into the nominal interest rate.",
                        hook="The real interest rate is 2 percent and expected inflation rises from 1 percent to 4 percent. What happens to the nominal rate in the Fisher relation, and what shifts in the loanable-funds market?",
                        hook_pair=(
                            ("fisher", "Nominal rate rises by about the rise in expected inflation, from about 3 percent to about 6 percent."),
                            ("demand", "Borrowers who expect to repay in cheaper dollars increase the demand for loanable funds, raising the nominal rate."),
                        ),
                        hook_hints=(
                            "Nominal is real plus expected inflation. Who wants to borrow more if repayment is cheaper?",
                            "A lender adds the expected melt of the dollar. A borrower is more willing to take the loan.",
                            "Fisher says the nominal rate ____. In the market, ____ shifts.",
                        ),
                        hook_trap=("real-rises", "Expected inflation raises the real rate one for one.", "The Fisher split puts the rise in the nominal rate."),
                        toy_prompt="Expected inflation rises and the real rate is unchanged. What happens to the nominal interest rate?",
                        choices=[
                            ("falls", "It falls, because inflation makes money easier.", "Easier repayment raises the nominal rate lenders require."),
                            ("rises", "It rises by about the rise in expected inflation.", ""),
                            ("stuck", "It cannot change if the real rate is unchanged.", "The nominal rate is the real rate plus expected inflation."),
                        ],
                        answer="rises",
                        toy_trap=("stuck-nominal", "A fixed real rate freezes the nominal rate.", "Expected inflation is the other term."),
                        gate="Why do lenders and borrowers put expected inflation into the nominal rate rather than into the real rate they think they are earning or paying?",
                        gate_pair=(
                            ("lenders", "Lenders add expected inflation so the real return they expect does not get inflated away."),
                            ("real-defined", "The real rate is what remains after expected inflation is stripped out of the nominal rate."),
                        ),
                        gate_hints=(
                            "If the dollar is expected to shrink, what does the lender tack onto the contract?",
                            "The contract is in dollars. The real rate is the leftover buying power.",
                            "Lenders add ____. The real rate is ____.",
                        ),
                        gate_trap=("real-is-contract", "The number written in the loan contract is the real rate.", "The contract number is nominal."),
                        flip="Contract Bot says a 6 percent loan rate is a 6 percent real return no matter the inflation forecast. Correct the split.",
                        flip_pair=(
                            ("nominal-contract", "The contract rate is nominal."),
                            ("subtract", "Expected inflation is subtracted to see the real rate."),
                        ),
                        flip_hints=(
                            "Ask what the dollars will buy when they are repaid.",
                            "Peel the forecast off the contract.",
                            "The 6 percent is ____. Real is ____.",
                        ),
                        flip_trap=("contract-real", "Whatever is written down is real by definition.", "Real is a construction from nominal and expected inflation."),
                    ),
                    standard(
                        "MAC-U3-Q2",
                        "T-Accounts and the Money Multiplier",
                        "core",
                        ["MAC-U3-Q1"],
                        ["money"],
                        "Ask how a new deposit becomes a larger change in the money supply when banks lend the excess.",
                        hook="A bank receives $1,000 of new reserves and must hold 10 percent. How much can it lend, and why can the banking system create more than $1,000 of deposits?",
                        hook_pair=(
                            ("excess", "Required reserves are $100, so this bank can lend $900 of excess reserves."),
                            ("system", "The loan is spent and redeposited, and later banks lend their excess, so the system multiplies deposits."),
                        ),
                        hook_hints=(
                            "What may this bank not lend, and where does the lent money go next?",
                            "One vault keeps a slice. The rest walks into the next vault.",
                            "This bank lends ____. The system creates more because ____.",
                        ),
                        hook_trap=("lend-all", "A 10 percent requirement lets the first bank lend the entire $1,000.", "It must keep the required slice."),
                        toy_prompt="The reserve requirement is 10 percent. A single bank gets $1,000 of new deposits. What can it lend?",
                        choices=[
                            ("thousand", "$1,000.", "That lends away the required reserves."),
                            ("nine-hundred", "$900.", ""),
                            ("ten-thousand", "$10,000.", "That is the simple system maximum, not this bank's loan."),
                        ],
                        answer="nine-hundred",
                        toy_trap=("confuse-system", "The first bank itself lends the whole money-multiplier result.", "The first bank lends only its excess. The system multiplies afterward."),
                        gate="Why does the simple money multiplier 1/rr overstate creation if people hold cash or banks hold excess reserves?",
                        gate_pair=(
                            ("cash", "Currency drain never gets redeposited, so it never becomes the next loan."),
                            ("excess", "Extra reserves banks refuse to lend are another leak, so the expansion is smaller than 1/rr."),
                        ),
                        gate_hints=(
                            "What has to happen to the loan before the next bank can multiply it?",
                            "Money under a mattress, and money a nervous bank will not lend.",
                            "Cash stops the chain because ____. Excess reserves stop it because ____.",
                        ),
                        gate_trap=("exact", "1/rr is the actual expansion in every economy.", "It is a maximum under two strong assumptions."),
                        flip="Vault Bot says a 10 percent rule turns $1,000 into $10,000 inside the first bank. Fix the T-account and the system.",
                        flip_pair=(
                            ("first", "The first bank lends $900, not $10,000."),
                            ("later", "The $10,000 figure is a system maximum only if every excess dollar is redeposited and lent."),
                        ),
                        flip_hints=(
                            "Draw two columns for the first bank only.",
                            "Then let the loan leave the building.",
                            "First bank: ____. System maximum: ____.",
                        ),
                        flip_trap=("one-bank", "One bank's balance sheet contains the whole multiplier.", "The multiplier is a chain of banks."),
                    ),
                    standard(
                        "MAC-U3-Q3",
                        "Ample vs Scarce Reserves Monetary Policy",
                        "core",
                        ["MAC-U3-Q2"],
                        ["money"],
                        "Ask how the Fed steers the policy rate when reserves are ample, and how open-market operations did it when reserves were scarce.",
                        hook="In an ample-reserves regime the Fed sets administered rates, including interest on reserve balances. In a scarce-reserves regime it used open-market operations. How does each tool move the policy rate?",
                        hook_pair=(
                            ("ample", "With ample reserves, raising interest on reserve balances sets a floor and lifts the policy rate without needing to drain a scarce supply."),
                            ("scarce", "With scarce reserves, selling securities in an open-market operation drains reserves and raises the federal funds rate."),
                        ),
                        hook_hints=(
                            "Is the Fed moving a price it pays, or changing the quantity of reserves?",
                            "A posted floor under a flooded market, versus taking chips off a tight table.",
                            "Ample: the Fed ____. Scarce: the Fed ____.",
                        ),
                        hook_trap=("one-tool", "Open-market operations are the only way the Fed has ever moved the policy rate.", "Ample reserves made administered rates the steering wheel."),
                        toy_prompt="Reserves are ample. What does the Fed do to raise the policy rate?",
                        choices=[
                            ("buy", "Buy bonds so reserves become even more plentiful and the rate rises.", "Buying adds reserves. In a scarce regime that would lower the rate."),
                            ("iorb", "Raise the interest rate it pays on reserve balances.", ""),
                            ("print-zero", "Set the reserve requirement to zero and hope.", "The administered rate, not a hope, is the tool."),
                        ],
                        answer="iorb",
                        toy_trap=("buy-raises", "Adding reserves raises the policy rate when reserves are already ample.", "Adding supply would not be how you lift a rate. The floor is the administered rate."),
                        gate="Why can a small open-market sale fail to move the policy rate once reserves are ample?",
                        gate_pair=(
                            ("flat", "The reserve-demand curve is flat in the ample region, so a modest quantity change does not change the rate."),
                            ("floor", "The rate is pinned by administered rates, not by a scarce intersection."),
                        ),
                        gate_hints=(
                            "What does the demand curve for reserves look like once banks already have more than enough?",
                            "Taking one bucket out of a lake does not raise the waterline price.",
                            "The curve is ____. The rate is set by ____.",
                        ),
                        gate_trap=("always-sale", "Any sale of securities raises the funds rate one for one, in every regime.", "That was the scarce-reserves story."),
                        flip="Desk Bot announces an open-market sale to hike rates in today's ample-reserves system. Redirect the bot to the tool that actually binds.",
                        flip_pair=(
                            ("not-sale", "A small sale is not the binding tool when reserves are ample."),
                            ("administered", "The Fed raises administered rates such as interest on reserve balances."),
                        ),
                        flip_hints=(
                            "Ask whether reserves are on the flat part of the curve.",
                            "Move the floor, do not pretend the lake is a puddle.",
                            "The sale fails to bind because ____. The hike is ____.",
                        ),
                        flip_trap=("always-omo", "The scarce-reserves playbook is still the whole playbook.", "The regime changed the tool."),
                    ),
                    standard(
                        "MAC-U3-BOSS",
                        "Liquidity Lab",
                        "capstone",
                        ["MAC-U3-Q3"],
                        ["money"],
                        "Ask your child to trace a policy-rate change from the Fed's tool to a borrower's loan.",
                        hook="The Fed wants a higher policy rate in an ample-reserves regime. Trace the path from the tool it uses to a bank's willingness to lend and then to the loanable-funds rate a firm pays.",
                        hook_pair=(
                            ("tool", "The Fed raises interest on reserve balances, lifting the policy rate."),
                            ("borrower", "Banks lend less eagerly at the higher opportunity cost of reserves, so the rate firms pay in loanable funds rises."),
                        ),
                        hook_hints=(
                            "What do banks compare a loan against once reserves pay more?",
                            "A higher floor makes the alternative to lending more attractive.",
                            "Tool: ____. The firm then faces ____.",
                        ),
                        hook_trap=("skips", "The policy rate and the rate a firm pays are unrelated prices.", "The lab wants the link."),
                        toy_prompt="Which path matches ample-reserves tightening?",
                        choices=[
                            ("omo-only", "Sell a few bonds, reserves stay ample, and that quantity change is what lifts every loan rate.", "Quantity is not the binding lever in the ample region."),
                            ("floor", "Raise interest on reserves, lift the policy rate, and pull up the cost of borrowing.", ""),
                            ("cut-iorb", "Cut interest on reserves in order to tighten.", "Cutting the floor is easing, not tightening."),
                        ],
                        answer="floor",
                        toy_trap=("direction", "Tightening means paying banks less on reserves.", "Tightening means a higher floor."),
                        gate="Why must this lab name both the reserve regime and the loanable-funds market?",
                        gate_pair=(
                            ("regime", "The regime picks the tool, administered rates versus open-market quantity."),
                            ("funds", "Loanable funds is where the policy rate becomes the firm's borrowing cost."),
                        ),
                        gate_hints=(
                            "One market is reserves. The other is saving and investment.",
                            "Do not stop at the Fed's press release.",
                            "The regime matters because ____. Loanable funds matters because ____.",
                        ),
                        gate_trap=("one-market", "The policy rate is set inside the loanable-funds diagram directly by the Treasury.", "The Fed's reserve tool reaches that diagram. It is not the Treasury's bond auction alone."),
                        flip="Lab Bot tightens by buying securities under ample reserves and says firms will pay less. Reverse the tool and the firm's rate.",
                        flip_pair=(
                            ("tool-fix", "Tightening in ample reserves raises administered rates."),
                            ("firm", "The firm's borrowing rate rises, not falls."),
                        ),
                        flip_hints=(
                            "Buying securities is the wrong direction even before the regime.",
                            "A higher floor does not cheapen loans.",
                            "The tool should ____. The firm pays ____.",
                        ),
                        flip_trap=("buy-tighten", "Buying securities tightens financial conditions.", "Buying adds reserves and is the easing operation in the scarce story, and it is not the ample-reserves hike."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                4,
                "Stabilization, Stagflation and the Phillips Curve",
                "Demand shocks move along the SRPC. Supply shocks shift the SRPC.",
                "The Fed changes the policy rate, as in MAC-U3-Q3, and aggregate demand and short-run aggregate supply shift, as in MAC-U2-Q2. A demand shock moves along the short-run Phillips curve, while a supply shock shifts the whole curve.",
                [
                    _central_banker(),
                    standard(
                        "MAC-U4-Q2",
                        "Short-Run vs Long-Run Phillips Curve and Expectations",
                        "core",
                        ["MAC-U4-Q1"],
                        ["phillips"],
                        "Ask why a short-run tradeoff disappears once expected inflation catches up.",
                        hook="The SRPC slopes down. The LRPC is vertical at the natural rate. Why can a surprise inflation cut unemployment only temporarily?",
                        hook_pair=(
                            ("surprise", "Unexpected inflation lowers real wages while nominal wages are sticky, so firms hire and unemployment falls along the SRPC."),
                            ("catch-up", "Once expected inflation rises, the SRPC shifts up and unemployment returns to the natural rate."),
                        ),
                        hook_hints=(
                            "What did workers fail to expect, and what do they write into the next contract?",
                            "A surprise discount on real wages, then a renegotiated contract.",
                            "Temporary because ____. The return happens when ____.",
                        ),
                        hook_trap=("permanent", "A central bank can hold unemployment below the natural rate forever by accepting higher inflation.", "Expectations catch up. The long-run curve is vertical."),
                        toy_prompt="What is the long-run Phillips curve?",
                        choices=[
                            ("down", "A downward-sloping permanent tradeoff.", "That is the short-run curve, and only while expectations are fixed."),
                            ("vertical", "Vertical at the natural rate of unemployment.", ""),
                            ("up", "Upward sloping through stagflation.", "Stagflation is a short-run shift, not the shape of the LRPC."),
                        ],
                        answer="vertical",
                        toy_trap=("tradeoff-forever", "The short-run slope is the long-run law.", "Expectations take the slope away."),
                        gate="How does a rise in expected inflation shift the SRPC, and where does the LRPC stay?",
                        gate_pair=(
                            ("shift-up", "Higher expected inflation shifts the SRPC up or right, so each unemployment rate comes with higher inflation."),
                            ("lrpc", "The LRPC stays vertical at the natural rate."),
                        ),
                        gate_hints=(
                            "Workers who expect more inflation need a higher nominal settlement at the same real wage.",
                            "The menu of the short run reprints. The long-run pole does not move.",
                            "SRPC shifts ____. LRPC ____.",
                        ),
                        gate_trap=("move-natural", "Expected inflation moves the natural rate one for one.", "The natural rate is not the expected-inflation knob."),
                        flip="Tradeoff Bot promises a permanent cut in unemployment from a permanent rise in inflation. Use expectations to rebut it.",
                        flip_pair=(
                            ("only-surprise", "Only unexpected inflation buys the short-run drop in unemployment."),
                            ("back", "When expectations catch up, unemployment returns to the natural rate."),
                        ),
                        flip_hints=(
                            "Separate the first contract from the second.",
                            "The discount expires.",
                            "The cut lasts only while ____. Then ____.",
                        ),
                        flip_trap=("promise", "A credible promise of higher inflation keeps unemployment down.", "A credible rise is expected, so it does not stay a surprise."),
                    ),
                    standard(
                        "MAC-U4-Q3",
                        "Fiscal Deficits and Crowding Out",
                        "core",
                        ["MAC-U4-Q2"],
                        ["ad-as", "money"],
                        "Ask how a deficit can raise interest rates and shrink the investment a fiscal boost was meant to support.",
                        hook="A deficit-financed spending increase shifts AD right. In the loanable-funds market, government borrowing rises. What happens to the real interest rate and to private investment?",
                        hook_pair=(
                            ("rate", "The real interest rate rises as public borrowing adds to the demand for funds."),
                            ("investment", "Higher rates crowd out interest-sensitive private investment, so the net AD shift is smaller than the simple multiplier."),
                        ),
                        hook_hints=(
                            "Who else is borrowing in the same pool of saving?",
                            "The government steps to the front of the loan line. Firms drop out as the price rises.",
                            "The real rate ____. Private investment ____.",
                        ),
                        hook_trap=("free", "Deficit spending has the full multiplier because the funds are public.", "The funds are still loanable funds, and firms feel the rate."),
                        toy_prompt="Crowding out shows up as which pair?",
                        choices=[
                            ("lower-rate", "A lower real interest rate and more private investment.", "That is the opposite of a government borrowing surge."),
                            ("higher-rate", "A higher real interest rate and less private investment.", ""),
                            ("lras", "A left shift of LRAS equal to the deficit.", "Crowding out is a rate and investment story, not an instant collapse of potential by the deficit's size."),
                        ],
                        answer="higher-rate",
                        toy_trap=("stimulus-only", "Deficits only shift AD and never touch the interest rate.", "The financing is the loanable-funds shift."),
                        gate="Why is the net multiplier smaller once crowding out is included?",
                        gate_pair=(
                            ("gross", "The government purchase starts a multiplied rise in AD."),
                            ("net", "Crowded-out investment is a fall in another component of AD, so the net shift is smaller."),
                        ),
                        gate_hints=(
                            "Which component of spending falls when the rate rises?",
                            "One shop gains a government order. Another loses a factory loan.",
                            "The gross effect is ____. The net effect is smaller because ____.",
                        ),
                        gate_trap=("larger", "Crowding out makes the multiplier larger.", "It offsets part of the shift."),
                        flip="Stimulus Bot quotes the simple multiplier and ignores the interest rate. Add crowding out to the bot's story.",
                        flip_pair=(
                            ("rate-up", "Deficit borrowing raises the real interest rate."),
                            ("investment-down", "Private investment falls and offsets part of the AD shift."),
                        ),
                        flip_hints=(
                            "Open the loanable-funds diagram next to the AD diagram.",
                            "The second diagram taxes the first.",
                            "The rate ____. Investment ____.",
                        ),
                        flip_trap=("simple-full", "The simple multiplier is the equilibrium result in a closed loanable-funds market.", "It is an upper sketch before crowding out."),
                    ),
                ],
            ),
            unit(
                5,
                "FOREX",
                "Interest rates drive capital flows and exchange rates, and the exchange rate then moves net exports.",
                "A rate change does not stop at the domestic Phillips curve. It moves capital across borders, the exchange rate, and then net exports.",
                [
                    standard(
                        "MAC-U5-BOSS",
                        "Course Finale — Fed rate hike, then FOREX capital flow, then net exports",
                        "capstone",
                        ["MAC-U4-Q3"],
                        ["forex", "phillips"],
                        "Ask your child to carry a Fed rate hike across the border into the exchange rate and net exports.",
                        hook="The Fed raises the policy rate. Trace three steps: the capital flow, the exchange rate, and net exports. Say which way each one moves.",
                        hook_pair=(
                            ("capital-fx", "Higher domestic rates attract foreign capital, so the currency appreciates."),
                            ("nx", "Appreciation makes exports dearer and imports cheaper, so net exports fall."),
                        ),
                        hook_hints=(
                            "Where do global savers put funds when one country's rate rises?",
                            "They buy the currency to buy the asset, and the stronger currency taxes exports.",
                            "Capital flows ____. The currency ____. Net exports ____.",
                        ),
                        hook_trap=("depreciate", "A rate hike floods the country with imports of its own currency and depreciates it.", "Inflow appreciation is the direction."),
                        toy_prompt="After a Fed rate hike, which chain is right?",
                        choices=[
                            ("out-down", "Capital flows out, the currency depreciates, and net exports rise.", "That is the easing chain, not the hike."),
                            ("in-up-down", "Capital flows in, the currency appreciates, and net exports fall.", ""),
                            ("in-down-up", "Capital flows in, the currency depreciates, and net exports rise.", "An inflow bids the currency up, not down."),
                        ],
                        answer="in-up-down",
                        toy_trap=("export-boom", "A stronger currency after a hike raises net exports.", "A stronger currency squeezes net exports."),
                        gate="Why does this foreign channel reinforce the domestic AD slowdown from a rate hike?",
                        gate_pair=(
                            ("domestic", "The hike already cuts interest-sensitive domestic spending, shifting AD left."),
                            ("foreign", "Lower net exports are a second leftward pull on AD."),
                        ),
                        gate_hints=(
                            "Name the domestic spending that falls, then the foreign component that falls.",
                            "Costlier loans at home, and a harder time selling abroad.",
                            "Domestic AD falls because ____. Net exports reinforce it because ____.",
                        ),
                        gate_trap=("offset", "The exchange-rate channel cancels the domestic effect of a hike.", "Both channels reduce AD."),
                        flip="Export Bot says a rate hike weakens the currency and boosts net exports, saving the expansion. Rebuild the three-step chain.",
                        flip_pair=(
                            ("appreciate", "Capital inflows appreciate the currency."),
                            ("nx-fall", "Net exports fall and reinforce the slowdown."),
                        ),
                        flip_hints=(
                            "Start from who buys the currency.",
                            "Then ask whether foreign customers find the goods cheaper or dearer.",
                            "The currency ____. Net exports ____.",
                        ),
                        flip_trap=("boost", "Hikes are an export-promotion tool via a weaker currency.", "The capital-flow sign runs the other way."),
                        flip_bloom="create",
                    ),
                ],
            ),
        ],
    )

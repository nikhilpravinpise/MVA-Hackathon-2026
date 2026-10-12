# Could an existing medicine help in MVA? What we looked at, and what we found

*A plain-language companion to our Track 2 report, written for families
and for the MVA Society Information Hub. It contains no information about
any child beyond what is already published in our Track 1 report. The
companion piece [FAMILY_EXPLAINER.md](../FAMILY_EXPLAINER.md) explains
what MVA is and how a genome points to an answer; this one is about
medicines.*

---

## Please read this first

**Nothing in this document is a treatment, and nothing here should be
given to anyone.** We are researchers in a hackathon, not this child's
doctors. What we have produced is a short list of medicines that already
exist for other conditions and that, on the biology, are worth *testing
in a laboratory* - starting with cells in a dish, not with people. Most
ideas that look good at this stage do not work out. That is normal, and
it is why the testing comes first.

Any decision about care belongs to the family and their clinical team.

## The idea in one paragraph

In MVA caused by changes in the *BUB1B* gene, cells are short of a
protein called BubR1, the inspector that checks chromosomes before a cell
divides. With too little of it, some cells end up with the wrong number
of chromosomes. We asked whether an already-approved medicine could help
at any point along that chain. Rather than guess, we built a program that
searches public drug and biology databases, kept only medicines that are
genuinely approved, and then checked every claim against the published
literature.

## Three ways to help, and why

Think of the problem in three stages, like a leak in a house.

**1. Fix the tap (we call this Rescue).** This child has one *BUB1B*
copy that is silent and one that still works, though less well. That
working copy is the entire supply. One caveat belongs here rather than in
a footnote: our Track 1 data could not show that the two changes sit on
*different* copies of the gene rather than on the same one. We assume they
are on different copies, because that is the pattern this condition
almost always takes, but nobody has shown it in this child, and a parental
test would settle it. If a medicine could help that copy
last longer or work a little better, it would address the cause rather
than the consequences. There is a known route: a vitamin-derived molecule
called NAD+ supports a protein that keeps BubR1 stable, and in mice bred
to have the same shortage, raising NAD+ helped. The approved form is a
form of vitamin B3. It is not approved for children, and whether it does
anything for this particular genetic change is exactly what a laboratory
test would tell us.

**2. Mop up the water (Remove).** Cells with the wrong number of
chromosomes often stop dividing and become "senescent" - worn out, still
alive, and leaking signals that irritate the tissue around them. In mice
with this same BubR1 shortage, clearing those worn-out cells delayed the
problems that followed. Two approaches exist in people today: medicines
that clear senescent cells, and medicines that quieten their signalling.

**3. Watch the house (Intercept).** Cells with the wrong chromosome
number are also the ones that can turn into cancer. One strand of
research asks whether certain approved medicines are harder on those
cells than on healthy ones. Alongside that, the most useful thing
available today is not a medicine at all: careful, scheduled cancer
screening, which is already recommended for conditions of this kind.

## What we are proposing be tested, honestly described

| Idea | What it is | Where it stands |
|---|---|---|
| Senolytic pair (dasatinib + quercetin) | Clears worn-out cells | The strongest supporting experiment was done in mice with this same BubR1 shortage. The medicine is approved for children with a form of leukaemia, but its label warns about effects on growth - a real concern here |
| Everolimus | Quietens worn-out cells' signalling | Has the clearest children's track record: approved from age one for a tumour condition, with no reported harm to growth or puberty over about four years. It does suppress the immune system |
| Niacin (vitamin B3) | Supports the working *BUB1B* copy | The only idea aimed at the cause. Evidence comes from mice, and the human form is not approved for children |
| Hydroxychloroquine | May be harder on cells with wrong chromosome numbers | The weakest evidence of the four, but the cheapest to test |

We also wrote down **sixteen ideas we rejected, and why**. One matters
for families to understand: growth hormone. It is an obvious thought when
a child is small, and we decided against proposing it, because it
encourages cells to grow at a time when some of those cells already carry
chromosome errors. That is a judgement about risk, not a proven harm, and
we say so in the report.

## How we tried to keep ourselves honest

We used AI assistants to do a great deal of this work, which makes it
fair to ask how much to trust the result. Three answers:

- **Every reference is checked by a program**, not by the AI's memory.
  Each paper we cite is looked up in the public medical literature
  database, confirmed to exist, confirmed not to have been retracted, and
  its title and year matched against what we claim it says.
- **Whether a medicine is really approved is checked against the
  regulators' own data**, not asserted.
- **We tested our own method.** We ran the same program on nine other
  diseases where the right answer is already known and published, and
  reported how often it found that answer, including the times it did
  not.

We also caught our own program being wrong in a way worth telling you
about. Left to itself, it put chemotherapy drugs at the top of the list,
because those drugs have the most research published about them. For a
child whose cells already struggle to divide correctly, that is close to
the worst possible suggestion. We added a rule that removes them, and we
publish the list of what was removed rather than quietly deleting it.

## What would actually happen next

The honest next step is small, cheap and quick. The MVA Society already
funds laboratories growing skin cells from families with MVA. Those cells
can be exposed to each candidate and measured: does the number of
chromosome errors go down, stay the same, or go up? We wrote the
threshold for each test in advance, including the one rule that overrides
everything else: **any candidate that increases chromosome errors is
dropped, whatever else it appears to do.**

Results of that kind would take a few weeks, and would tell researchers
which of these ideas deserve more work and which should be abandoned.
That is the point of this document: not an answer, but a short list worth
the effort of testing, and a clear way to be proven wrong.

---

*This work was made possible through the Hackathon, organized by Sage
Bionetworks in partnership with the MVA Society, Hugging Face, and BEACON
(The Benchmarking, Evaluation, and Assessment Consortium for Science),
with prize sponsorship from AWS and Anthropic. We are deeply grateful to
the child and their family who generously contributed their data and
their story to advance research into this rare disease. We acknowledge
their trust in making this Hackathon possible.*

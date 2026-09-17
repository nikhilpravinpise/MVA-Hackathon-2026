"""Overview/About tab.

Due to the logos and need for layout control, this tab is written in raw HTML
rather than markdown. To update text content, edit _build_html() below.
"""

from __future__ import annotations

import gradio as gr

from config import DATASET_URL, DISCUSSIONS_URL


def _build_html(img_child: str) -> str:
    story_figure = f"""
      <figure class="story-figure">
        <img
          src="{img_child}"
          alt="A child's drawing of himself smiling in a hospital bed"
          class="story-drawing">
        <figcaption>Illustration courtesy of the
          <a href="https://mvasociety.org" target="_blank" rel="noopener">MVA Society</a>
        </figcaption>
      </figure>""" if img_child else ""

    return f"""
<main>

  <section id="about" class="section">
    <div class="container">
      <p>
        Every person's DNA contains millions of tiny variations, and almost all of them are harmless. But
        every so often, one of those variations disrupts something important, and the result is a disease.
        For many rare diseases, doctors and researchers recognize the symptoms but don't know the exact
        genetic variations responsible for them.
      </p>
      <p>
        This MVA Hackathon releases real genetic and clinical data, shared with full, explicit
        permission from the family it belongs to, and asks the global research community to help make sense
        of it.
      </p>
      <p>
        Access to the data is controlled. The research outputs are open: participant
        submissions, code, and reports are released under CC BY 4.0, so methods developed for this
        case can be reused for other undiagnosed individuals.
      </p>
    </div>
  </section>

  <section id="story" class="section section-alt">
    <div class="container story-container">
      <div class="story-text">
        <h2>Why This Hackathon Exists</h2>
        <p>
          Behind this project is a family who made a deeply personal decision: to share their child's most
          private information - their genome - with strangers around the world, in the hope that someone,
          somewhere, might help understand their child's rare condition.
        </p>
        <p>
          Their child lives with <strong>Mosaic Variegated Aneuploidy (MVA)</strong>, a condition few
          clinicians will ever encounter in their careers. There is currently no established treatment, but
          the MVA Society is funding focused research to bring treatments closer. Care today means managing
          symptoms and fighting cancer cells.
        </p>
      </div>
      {story_figure}
    </div>
  </section>

  <section id="tracks" class="section">
    <div class="container">
      <h2>Two Tracks</h2>
      <div class="card-grid">

        <div class="info-card track-card">
          <h3>🧬 Track 1 - Variant Prediction</h3>
          <div class="track-goal">
            <strong>The Goal:</strong> Predict the specific genetic variant(s) that may be driving the child's
            condition using their clinical symptoms and genomic data.
          </div>
          <p>
            You'll be given the child's genomic data (FASTQ + VCF) and a description of their symptoms, and asked to
            predict which specific variant(s) may be causing the condition. Secondary or incidental findings are
            welcome too.
          </p>
          <p>
            Your ranked predictions are automatically checked against the clinically confirmed answer
            and your score updates live on the public leaderboard.
          </p>
          <ul class="note-small">
            <li>What you submit: A ranked list of variant predictions, a Github link, and a methods writeup.</li>
            <li>Submission limit: 6</li>
          </ul>
          <span class="sub-heading">Scoring</span>
          <p>
            <strong>This is a foundational track</strong> — the goal is to validate that your pipeline can
            recover a clinically confirmed variant from real patient data. Prediction files are scored automatically on
            two primary metrics:
          </p>
          <ul>
            <li><strong>Rank points</strong> - How high did you rank the true variant(s). If your top-ranked
            variant(s) is correct, you'll get 100pts. If you get the correct variant(s) within your top 10
            ranked ones, you'll get partial credit. If you correctly identify one of the two variants in a
            heterozygous pair, you'll get half credit.</li>
            <li><strong>F-max</strong> - the best balance of precision and recall your submission achieves at
            any confidence threshold, rewarding submissions that pinpoint the right answer without burying it
            in noise. Secondary or incidental findings won't hurt your automated score.</li>
          </ul>
          <p>
            Your <strong>methods write-up</strong> is reviewed separately by a judging panel for scientific rigor and
            depth of understanding.
          </p>
        </div>

        <div class="info-card track-card">
          <h3>💊 Track 2 - Drug Repurposing</h3>
          <div class="track-goal">
            <strong>The Goal:</strong> Identify existing, approved medications that are plausible
            candidates for further investigation, based on the biological mechanisms disrupted in this
            case. Submissions are hypotheses for follow-up, not evidence that a medicine works.
          </div>
          <p>
            Once you know (or have a strong guess at) what biological mechanisms are involved, the next question
            is: Does an existing medication work on this biological problem? 
          </p>
          <p>
            For this track, you'll characterize the mechanism behind the variant(s) and write up your reasoning
            and proposed candidate medication(s). An independent panel of expert judges evaluates submissions on
            scientific merit and real-world potential.
          </p>
          <ul class="note-small">
            <li>What you submit: A detailed report, a Github link, and a 3-minute pitch video</li>
            <li>Submission limit: 3</li>
          </ul>
          <span class="sub-heading">Scoring</span>
          <p>
            Track 2 is scored by our expert panel across four weighted criteria:
          </p>
          <!-- Hiding for now, I dont think it adds much value
          <div class="criteria-stacked-bar" aria-hidden="true">
            <div class="csb-seg" style="--w:35%; --c:#1f9bea" data-tip="Scientific Rigor - 35%"></div>
            <div class="csb-seg" style="--w:25%; --c:#59c959" data-tip="Potential Impact - 25%"></div>
            <div class="csb-seg" style="--w:25%; --c:#7b5ea7" data-tip="Innovation - 25%"></div>
            <div class="csb-seg" style="--w:15%; --c:#e0509a" data-tip="Scalability - 15%"></div>
          </div>
          -->
          <div class="criteria-list">
            <div class="criterion">
              <div class="criterion-label">
                <span>
                  <span class="criterion-swatch" style="--c:#1f9bea"></span>
                  <strong>Scientific Rigor</strong>
                </span>
                <strong>35%</strong>
              </div>
              <p class="criterion-desc">
                Is the variant mechanism characterization sound, and is the proposed drug repurposing
                candidate well-supported by that mechanism?
              </p>
            </div>
            <div class="criterion">
              <div class="criterion-label">
                <span>
                  <span class="criterion-swatch" style="--c:#59c959"></span>
                  <strong>Potential Impact</strong>
                </span>
                <strong>25%</strong>
              </div>
              <p class="criterion-desc">
                If independently validated, how much could this contribute to understanding or
                diagnosing MVA, for this child or for others living with it?
              </p>
            </div>
            <div class="criterion">
              <div class="criterion-label">
                <span>
                  <span class="criterion-swatch" style="--c:#7b5ea7"></span>
                  <strong>Innovation</strong>
                </span>
                <strong>25%</strong>
              </div>
              <p class="criterion-desc">
                Did you bring a genuinely creative angle, method, or tool to the problem?
              </p>
            </div>
            <div class="criterion">
              <div class="criterion-label">
                <span>
                  <span class="criterion-swatch" style="--c:#e0509a"></span>
                  <strong>Scalability</strong>
                </span>
                <strong>15%</strong>
              </div>
              <p class="criterion-desc">
                Could your approach realistically be applied to other individuals, other diseases, or larger
                datasets - not just this one case?
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  </section>

  <section id="prizes" class="section">
    <div class="container">
      <h2>Prizes</h2>
      <p>
        <strong>$50,000 total</strong> - $25,000 in cash from the AWS Imagine Grant program + $25,000 in Claude credits from Anthropic*.
      </p>
      <div class="prize-grid">
        <div class="prize-card gold">
          <div class="prize-place">🥇 1st Place</div>
          <div class="prize-amount">1x $12,000 cash</div>
          <div class="prize-amount">1x $12,000 credits</div>
        </div>
        <div class="prize-card silver">
          <div class="prize-place">🥈 2nd Place</div>
          <div class="prize-amount">1x $7,000 cash</div>
          <div class="prize-amount">1x $7,000 credits</div>
        </div>
        <div class="prize-card bronze">
          <div class="prize-place">🥉 3rd Place</div>
          <div class="prize-amount">1x $4,000 cash</div>
          <div class="prize-amount">1x $4,000 credits</div>
        </div>
        <div class="prize-card special">
          <div class="prize-place">🌟 Innovation</div>
          <div class="prize-amount">1x $2,000 cash</div>
          <div class="prize-amount">1x $2,000 credits</div>
        </div>
      </div>
      <p class="note-small"><em>
        *Anthropic credits are provided for use with Claude Science, intended to help winning teams deepen
        their computational analysis and extend their findings on MVA beyond the Hackathon itself, not as a
        cash-equivalent award.
      </em></p>
    </div>
  </section>

  <section id="how-to-participate" class="section section-alt">
    <div class="container">
      <h2>How to Participate</h2>
      <p>
        Anyone can join, and no previous hackathon experience is needed. The tracks are built for a
            mix of backgrounds: ML engineers and computational biologists, clinicians and geneticists,
            students and citizen scientists.
      </p>
      <ol class="steps">
        <li>
          <span class="step-num">1</span>
          <div>
            <strong>Sign in</strong>
            <p>
              Log in with your Hugging Face account. Don't have one? <a href="https://huggingface.co/join" target="_blank" rel="noopener">Create one for free</a>.
            </p>
          </div>
        </li>
        <li>
          <span class="step-num">2</span>
          <div>
            <strong>Get the data</strong>
            <p>
              Because the data comes from a real person, you must first request access. Fill out the
              short form on the <a href="{DATASET_URL}" target="_blank" rel="noopener">dataset page</a>
              confirming you understand and agree to the data usage rules. The data is shared under a
              protocol approved by WCG IRB (protocol #20252010).
            </p>
          </div>
        </li>
        <li>
          <span class="step-num">3</span>
          <div>
            <strong>Choose your track</strong>
            <p>
              Decide whether you want to try identifying the causal variant (Track 1), propose a
              repurposed medication (Track 2), or take on both - many teams do. You don't need to
              finish one to start the other.
            </p>
          </div>
        </li>
        <li>
          <span class="step-num">4</span>
          <div>
            <strong>Build and submit</strong>
            <p>
              Work through the data at your own pace using whatever tools, software, or methods you prefer.
              When ready, navigate to the "Submit - Track 1" or "Submit - Track 2" tabs for instructions and
              submission guidelines.
            </p>
          </div>
        </li>
        <li>
          <span class="step-num">5</span>
          <div>
            <strong>Join the community</strong>
            <p>
              Have questions or want to connect with other participants? Join the conversation on the
              <a href="{DISCUSSIONS_URL}" target="_blank" rel="noopener">Community page</a>.
            </p>
          </div>
        </li>
      </ol>
    </div>
  </section>

<section id="timeline" class="section">
  <div class="container">
    <h2>Timeline</h2>
    <p>
      Dates are subject to change. Any updates to key milestones will be reflected in this table
      posted to the <a href="{DISCUSSIONS_URL}" target="_blank" rel="noopener">Community page</a>.
    </p>
    <table class="timeline-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Milestone</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>August 24</td>
          <td>Hackathon launch; dataset available for request and download</td>
        </tr>
        <tr>
          <td>August 25</td>
          <td>Submissions open</td>
        </tr>
        <tr>
          <td>October 24 (23:59 UTC)</td>
          <td>Submissions close; Track 1 leaderboard frozen</td>
        </tr>
        <tr>
          <td>October 24 - November 24</td>
          <td>Track 1 qualitative evaluation; Track 2 expert panel judging</td>
        </tr>
        <tr>
          <td>November 25</td>
          <td>Winners announced; prizes awarded</td>
        </tr>
      </tbody>
    </table>
  </div>
</section>

<section id="acknowledgements" class="section section-alt">
  <div class="container">
    <h2>Acknowledgements</h2>
    <p>
      We are deeply grateful to the child and their family who chose to share their genomic data openly
      with the research community. This hackathon would not exist without their generosity and trust.
    </p>
    <p>
      This hackathon was organized in partnership with
          <a href="https://sagebionetworks.org" target="_blank" rel="noopener">Sage Bionetworks</a>,
          the <a href="https://mvasociety.org" target="_blank" rel="noopener">MVA Society</a>,
          <a href="https://huggingface.co" target="_blank" rel="noopener">Hugging Face</a>,
          and <a href="https://conscience.ca/beacon/" target="_blank" rel="noopener">BEACON</a>
          (The Benchmarking, Evaluation, and Assessment Consortium for Science),
          with prize sponsorship from
          <a href="https://aws.amazon.com" target="_blank" rel="noopener">AWS</a>
          and <a href="https://www.anthropic.com" target="_blank" rel="noopener">Anthropic</a>.
        </p>
    <p>
      We thank the <a href="https://wilhelmfoundation.org" target="_blank" rel="noopener">Wilhelm Foundation</a>
      for their guidance and insight on this project.
    </p>
  </div>
</section>

  <div class="back-to-top-row">
    <a class="back-to-top" href="javascript:void(0)" onclick="document.getElementById('page-top').scrollIntoView({{behavior:'smooth'}})">↑ Back to top</a>
  </div>

</main>
"""


def render(img_child: str = "") -> None:
    with gr.Tab("Overview"):
        gr.HTML(_build_html(img_child))




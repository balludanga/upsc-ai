import { useEffect, useState } from 'react'
import './StudyRoom.css'

const API =
  import.meta.env.VITE_API_URL ||
  localStorage.getItem('upsc_api_url') ||
  'http://localhost:8000'

async function request(path, options = {}, token) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token
        ? { Authorization: `Bearer ${token}` }
        : {}),
      ...(options.headers || {}),
    },
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(
      data.detail ||
      'The assistant could not complete that request.'
    )
  }

  return data
}


function Auth({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setError('')

    try {
      if (mode === 'register') {
        await request(
          '/auth/register',
          {
            method: 'POST',
            body: JSON.stringify({
              email,
              password,
            }),
          }
        )
      }

      const body = new URLSearchParams({
        username: email,
        password,
      })

      const response = await fetch(
        `${API}/auth/login`,
        {
          method: 'POST',
          headers: {
            'Content-Type':
              'application/x-www-form-urlencoded',
          },
          body,
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || 'Could not sign in.'
        )
      }

      onLogin(data.access_token, email)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not sign in.'
      )
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-intro">
        <span className="kicker">PRIVATE STUDY ROOM</span>
        <h1>
          Build the answer
          <br />
          <i>before the exam.</i>
        </h1>
        <p>
          A focused workspace for grounded revision,
          active recall, and the small daily proof
          that you showed up.
        </p>
      </div>

      <form
        className="auth-panel"
        onSubmit={submit}
      >
        <div className="auth-switch">
          <button
            type="button"
            className={
              mode === 'login'
                ? 'selected'
                : ''
            }
            onClick={() => setMode('login')}
          >
            Sign in
          </button>

          <button
            type="button"
            className={
              mode === 'register'
                ? 'selected'
                : ''
            }
            onClick={() => setMode('register')}
          >
            Create account
          </button>
        </div>

        <label>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
          />
        </label>

        <label>
          Password
          <input
            type="password"
            required
            minLength="8"
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
          />
        </label>

        <button
          className="dark-button"
          type="submit"
        >
          {mode === 'login'
            ? 'Enter study room'
            : 'Create private account'}
          <b>-</b>
        </button>

        <p className="error">{error}</p>
      </form>
    </main>
  )
}


function Heading({ kicker, title }) {
  return (
    <div className="heading">
      <div>
        <span className="kicker">{kicker}</span>
        <h1>{title}</h1>
      </div>
    </div>
  )
}


function Overview({
  dashboard,
  plan,
  setPanel,
}) {
  const metrics = [
    [
      'Today',
      dashboard?.today_minutes || 0,
      'minutes focused',
    ],
    [
      'All time',
      dashboard?.total_minutes || 0,
      'minutes invested',
    ],
    [
      'Streak',
      dashboard?.current_streak_days || 0,
      'consecutive days',
    ],
    [
      'Accuracy',
      `${dashboard?.quiz_accuracy_percent || 0}%`,
      `${dashboard?.quizzes_attempted || 0} answered`,
    ],
  ]

  return (
    <section>
      <div className="heading">
        <div>
          <span className="kicker">
            TODAY /{' '}
            {new Date()
              .toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
              })
              .toUpperCase()}
          </span>
          <h1>Make the next hour count.</h1>
        </div>

        <button
          className="outline-button"
          onClick={() => setPanel('log')}
        >
          Log study time +
        </button>
      </div>

      <div className="metrics">
        {metrics.map(
          ([label, value, note]) => (
            <article key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
              <small>{note}</small>
            </article>
          )
        )}
      </div>

      <div className="columns">
        <article className="surface">
          <span className="kicker">
            THE NEXT 90 MINUTES
          </span>
          <h3>Today's plan</h3>

          {plan?.items?.map(
            (item, index) => (
              <div
                className="plan-item"
                key={`${item.topic}-${index}`}
              >
                <small>
                  {String(index + 1).padStart(2, '0')}
                  {' / '}
                  {item.minutes}m
                </small>

                <div>
                  <b>{item.topic}</b>
                  <p>{item.reason}</p>
                </div>

                <em>{item.mode}</em>
              </div>
            )
          )}
        </article>

        <article className="surface">
          <span className="kicker">REVISIT</span>
          <h3>Weak topics</h3>

          <div className="tags">
            {dashboard?.weak_topics?.length
              ? dashboard.weak_topics.map(
                  topic => (
                    <span key={topic}>
                      {topic}
                    </span>
                  )
                )
              : (
                <p className="muted">
                  Answer a quiz to reveal weak areas.
                </p>
              )}
          </div>
        </article>
      </div>
    </section>
  )
}


function AnswerText({
  answer,
}) {
  return (
    <div className="answer-content point-wise-answer">
      {answer}
    </div>
  )
}


function MainsDraft({ token }) {
  const [papers, setPapers] = useState([])
  const [selectedPaper, setSelectedPaper] =
    useState('GS2')
  const [question, setQuestion] = useState('')
  const [wordLimit, setWordLimit] =
    useState(250)
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function loadPapers() {
      try {
        const data = await request(
          '/mains/papers',
          {},
          token
        )

        setPapers(data.papers || [])
      } catch (err) {
        setMessage(
          err instanceof Error
            ? err.message
            : 'Could not load papers.'
        )
      }
    }

    loadPapers()
  }, [token])

  async function draftAnswer(event) {
    event.preventDefault()

    if (!question.trim()) return

    setLoading(true)
    setAnswer(null)
    setMessage('')

    try {
      const data = await request(
        '/mains/draft',
        {
          method: 'POST',
          body: JSON.stringify({
            question,
            paper: selectedPaper,
            word_limit: wordLimit,
          }),
        },
        token
      )

      setAnswer(data)
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not draft answer.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <Heading
        kicker="MAINS ANSWER DRAFTING"
        title="Paper-specific answer builder."
      />

      <p className="tool-intro">
        Generate a corpus-grounded, point-wise
        UPSC answer matched to the question demand.
      </p>

      <form
        className="mains-form"
        onSubmit={draftAnswer}
      >
        <div className="form-row">
          <label>
            <span>Paper</span>
            <select
              value={selectedPaper}
              onChange={event =>
                setSelectedPaper(event.target.value)
              }
            >
              {papers.map(p => (
                <option
                  key={p.id}
                  value={p.id}
                >
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Word Limit</span>
            <select
              value={wordLimit}
              onChange={event =>
                setWordLimit(
                  Number(event.target.value)
                )
              }
            >
              <option value={150}>
                150 words
              </option>
              <option value={250}>
                250 words
              </option>
              <option value={300}>
                300 words
              </option>
              <option value={500}>
                500 words
              </option>
              <option value={800}>
                800 words
              </option>
              <option value={1000}>
                1000 words
              </option>
            </select>
          </label>
        </div>

        <label className="wide">
          <span>Question</span>
          <textarea
            required
            minLength="3"
            value={question}
            onChange={event =>
              setQuestion(event.target.value)
            }
            placeholder="Critically examine the role of fiscal federalism in strengthening cooperative federalism."
          />
        </label>

        <button
          className="dark-button"
          type="submit"
          disabled={loading}
        >
          {loading
            ? 'Drafting...'
            : 'Draft mains answer'}
          <b>-</b>
        </button>
      </form>

      {message && (
        <div
          className="notice"
          onClick={() => setMessage('')}
        >
          {message}
        </div>
      )}

      {answer && (
        <article className="surface answer">
          <div className="answer-header">
            <div>
              <span className="kicker">
                {answer.paper}
              </span>

              <span
                className="kicker"
                style={{
                  marginLeft: '12px',
                }}
              >
                ~{answer.word_limit} words
              </span>

              <span
                className="kicker"
                style={{
                  marginLeft: '12px',
                }}
              >
                {answer.structure?.word_count || 0}
                {' '}
                words generated
              </span>
            </div>
          </div>

          <div className="answer-structure">
            {answer.structure?.has_introduction && (
              <span className="structure-badge">
                Introduction
              </span>
            )}

            {answer.structure?.has_body && (
              <span className="structure-badge">
                Point-wise Body
              </span>
            )}

            {answer.structure?.has_conclusion && (
              <span className="structure-badge">
                Conclusion
              </span>
            )}
          </div>

          <AnswerText answer={answer.answer} />
        </article>
      )}
    </section>
  )
}


function EvaluationBoolean({
  label,
  value,
}) {
  return (
    <div className="evaluation-check">
      <span>{value ? '✓' : '○'}</span>
      <b>{label}</b>
    </div>
  )
}


function EvaluationList({
  title,
  items,
}) {
  if (!items?.length) return null

  return (
    <div className="evaluation-section">
      <h4>{title}</h4>
      <ul>
        {items.map(
          (item, index) => (
            <li key={`${item}-${index}`}>
              {item}
            </li>
          )
        )}
      </ul>
    </div>
  )
}


function MainsEvaluate({ token }) {
  const [question, setQuestion] = useState('')
  const [paper, setPaper] = useState('GS2')
  const [wordLimit, setWordLimit] =
    useState(250)
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  async function evaluate(event) {
    event.preventDefault()

    if (!question.trim() || !answer.trim()) {
      setMessage(
        'Enter both the question and your answer.'
      )
      return
    }

    setLoading(true)
    setResult(null)
    setMessage('')

    try {
      const data = await request(
        '/mains/evaluate',
        {
          method: 'POST',
          body: JSON.stringify({
            question,
            answer,
            paper,
            word_limit: wordLimit,
          }),
        },
        token
      )

      setResult(data)
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not evaluate answer.'
      )
    } finally {
      setLoading(false)
    }
  }

  const evaluation = result?.evaluation

  return (
    <section>
      <Heading
        kicker="MAINS ANSWER EVALUATION"
        title="Write first. Then get feedback."
      />

      <p className="tool-intro">
        Evaluate question demand, structure,
        dimension coverage, analysis, evidence,
        keywords and conclusion without replacing
        your answer with an AI-written one.
      </p>

      <form
        className="surface evaluation-form"
        onSubmit={evaluate}
      >
        <div className="form-row">
          <label>
            <span>Paper</span>
            <select
              value={paper}
              onChange={event =>
                setPaper(event.target.value)
              }
            >
              <option value="GS1">GS1</option>
              <option value="GS2">GS2</option>
              <option value="GS3">GS3</option>
              <option value="GS4">GS4</option>
              <option value="ESSAY">Essay</option>
              <option value="OPTIONAL">
                Optional
              </option>
            </select>
          </label>

          <label>
            <span>Word Limit</span>
            <select
              value={wordLimit}
              onChange={event =>
                setWordLimit(
                  Number(event.target.value)
                )
              }
            >
              <option value={150}>
                150 words
              </option>
              <option value={250}>
                250 words
              </option>
              <option value={300}>
                300 words
              </option>
              <option value={500}>
                500 words
              </option>
              <option value={800}>
                800 words
              </option>
              <option value={1000}>
                1000 words
              </option>
            </select>
          </label>
        </div>

        <label className="wide">
          <span>Question</span>
          <textarea
            required
            value={question}
            onChange={event =>
              setQuestion(event.target.value)
            }
            placeholder="Enter the UPSC question..."
          />
        </label>

        <label className="wide">
          <span>Your Answer</span>
          <textarea
            className="evaluation-answer-input"
            required
            value={answer}
            onChange={event =>
              setAnswer(event.target.value)
            }
            placeholder="Write your answer here. Try to answer first without seeing an AI draft."
          />
          <small className="word-counter">
            {answer.trim()
              ? answer.trim().split(/\s+/).length
              : 0}
            {' '}
            words
          </small>
        </label>

        <button
          className="dark-button"
          type="submit"
          disabled={loading}
        >
          {loading
            ? 'Evaluating...'
            : 'Evaluate my answer'}
          <b>-</b>
        </button>
      </form>

      {message && (
        <div
          className="notice"
          onClick={() => setMessage('')}
        >
          {message}
        </div>
      )}

      {evaluation && (
        <article className="evaluation-results">
          <div className="surface evaluation-hero">
            <span className="kicker">
              FEEDBACK
            </span>

            <h3>
              {evaluation.overall_feedback}
            </h3>

            <div className="evaluation-checks">
              <EvaluationBoolean
                label="Question demand"
                value={
                  evaluation.question_demand
                    ?.addressed
                }
              />
              <EvaluationBoolean
                label="Introduction"
                value={
                  evaluation.structure
                    ?.introduction
                }
              />
              <EvaluationBoolean
                label="Point-wise body"
                value={
                  evaluation.structure
                    ?.point_wise
                }
              />
              <EvaluationBoolean
                label="Conclusion"
                value={
                  evaluation.structure
                    ?.conclusion
                }
              />
            </div>

            <p className="evaluation-note">
              {evaluation.question_demand
                ?.feedback}
            </p>
          </div>

          <div className="columns">
            <article className="surface">
              <span className="kicker">
                DIMENSIONS
              </span>

              <EvaluationList
                title="Covered"
                items={
                  evaluation.dimensions
                    ?.covered
                }
              />

              <EvaluationList
                title="Missing"
                items={
                  evaluation.dimensions
                    ?.missing
                }
              />

              <p className="evaluation-note">
                {evaluation.dimensions
                  ?.feedback}
              </p>
            </article>

            <article className="surface">
              <span className="kicker">
                ANALYSIS
              </span>

              <EvaluationList
                title="Strengths"
                items={
                  evaluation.analysis
                    ?.strengths
                }
              />

              <EvaluationList
                title="Weaknesses"
                items={
                  evaluation.analysis
                    ?.weaknesses
                }
              />

              <p className="evaluation-note">
                {evaluation.analysis
                  ?.feedback}
              </p>
            </article>
          </div>

          <div className="columns">
            <article className="surface">
              <span className="kicker">
                EVIDENCE
              </span>

              <EvaluationList
                title="Supported strengths"
                items={
                  evaluation.evidence
                    ?.strengths
                }
              />

              <EvaluationList
                title="Claims to verify"
                items={
                  evaluation.evidence
                    ?.unsupported_claims
                }
              />

              <p className="evaluation-note">
                {evaluation.evidence
                  ?.feedback}
              </p>
            </article>

            <article className="surface">
              <span className="kicker">
                IMPROVEMENT BANK
              </span>

              <EvaluationList
                title="Keywords to add"
                items={
                  evaluation.keywords_to_add
                }
              />

              <EvaluationList
                title="Examples to consider"
                items={
                  evaluation.examples_to_add
                }
              />

              <EvaluationList
                title="Next improvements"
                items={
                  evaluation.improvements
                }
              />
            </article>
          </div>

          <div className="surface evaluation-meta">
            <span>
              {evaluation.word_count || 0}
              {' '}
              words written
            </span>

            <span>
              Limit: {result.word_limit}
            </span>
          </div>
        </article>
      )}
    </section>
  )
}


function StudyRoom({
  token,
  email,
  onLogout,
}) {
  const [panel, setPanel] =
    useState('overview')
  const [dashboard, setDashboard] =
    useState(null)
  const [plan, setPlan] =
    useState(null)
  const [question, setQuestion] =
    useState('')
  const [answer, setAnswer] =
    useState(null)
  const [topic, setTopic] =
    useState('')
  const [quiz, setQuiz] =
    useState(null)
  const [results, setResults] =
    useState({})
  const [session, setSession] = useState({
    topic: '',
    mode: 'study',
    minutes: 45,
    notes: '',
  })
  const [message, setMessage] =
    useState('')

  async function refresh() {
    try {
      const [
        nextDashboard,
        nextPlan,
      ] = await Promise.all([
        request(
          '/study/dashboard',
          {},
          token
        ),
        request(
          '/study/plan',
          {},
          token
        ),
      ])

      setDashboard(nextDashboard)
      setPlan(nextPlan)
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not load dashboard.'
      )
    }
  }

  useEffect(() => {
    refresh()
  }, [token])

  async function ask(event) {
    event.preventDefault()

    if (!question.trim()) return

    setAnswer(
      'Preparing a corpus-grounded answer...'
    )

    try {
      const data = await request(
        '/ask',
        {
          method: 'POST',
          body: JSON.stringify({
            question,
          }),
        },
        token
      )

      setAnswer(data.answer)
    } catch (err) {
      setAnswer(
        err instanceof Error
          ? err.message
          : 'Could not answer that question.'
      )
    }
  }

  async function generateQuiz(event) {
    event.preventDefault()
    setQuiz(null)

    try {
      const data = await request(
        '/quiz/generate',
        {
          method: 'POST',
          body: JSON.stringify({
            topic,
            num_questions: 5,
          }),
        },
        token
      )

      setQuiz(data.questions)
      setResults({})
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not generate quiz.'
      )
    }
  }

  async function submitAnswer(
    id,
    optionIndex
  ) {
    const selected = String.fromCharCode(
      65 + optionIndex
    )

    try {
      const data = await request(
        '/quiz/submit',
        {
          method: 'POST',
          body: JSON.stringify({
            quiz_attempt_id: id,
            selected_option: selected,
          }),
        },
        token
      )

      setResults(prev => ({
        ...prev,
        [id]: data.correct
          ? 'Correct. Keep going.'
          : `Not quite. Answer: ${data.correct_option}`,
      }))

      refresh()
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not submit answer.'
      )
    }
  }

  async function logSession(event) {
    event.preventDefault()

    try {
      await request(
        '/study/sessions',
        {
          method: 'POST',
          body: JSON.stringify({
            ...session,
            minutes: Number(session.minutes),
            notes: session.notes || null,
          }),
        },
        token
      )

      setMessage(
        'Session saved. Dashboard updated.'
      )

      setSession({
        topic: '',
        mode: 'study',
        minutes: 45,
        notes: '',
      })

      refresh()
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not save session.'
      )
    }
  }

  const navItems = [
    ['overview', '01', 'Overview'],
    ['ask', '02', 'Ask'],
    ['mains', '03', 'Mains Drafting'],
    [
      'evaluate',
      '04',
      'Answer Evaluation',
    ],
    ['quiz', '05', 'Prelims Drill'],
    ['log', '06', 'Log a session'],
  ]

  return (
    <div className="room">
      <header className="header">
        <div>
          <span className="kicker">
            UPSC / PERSONAL CONSOLE
          </span>
          <h2>Study Room</h2>
        </div>

        <div className="header-right">
          <span>{email}</span>
          <button onClick={onLogout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="layout">
        <nav className="nav">
          {navItems.map(
            ([key, number, label]) => (
              <button
                key={key}
                className={
                  panel === key
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setPanel(key)
                }
              >
                <small>{number}</small>
                {label}
              </button>
            )
          )}
        </nav>

        <section className="main">
          {message && (
            <div
              className="notice"
              onClick={() => setMessage('')}
            >
              {message}
            </div>
          )}

          {panel === 'overview' && (
            <Overview
              dashboard={dashboard}
              plan={plan}
              setPanel={setPanel}
            />
          )}

          {panel === 'ask' && (
            <section>
              <Heading
                kicker="CORPUS / UNDERSTAND"
                title="Ask your corpus."
              />

              <p className="tool-intro">
                Ask a question and get a concise,
                corpus-grounded explanation.
              </p>

              <form
                className="ask-box"
                onSubmit={ask}
              >
                <textarea
                  required
                  minLength="3"
                  value={question}
                  onChange={event =>
                    setQuestion(
                      event.target.value
                    )
                  }
                  placeholder="Explain fiscal federalism in India..."
                />

                <button
                  className="dark-button"
                  type="submit"
                >
                  Ask
                  <b>-</b>
                </button>
              </form>

              {answer && (
                <article className="surface answer">
                  <AnswerText
                    answer={answer}
                  />
                </article>
              )}
            </section>
          )}

          {panel === 'mains' && (
            <MainsDraft token={token} />
          )}

          {panel === 'evaluate' && (
            <MainsEvaluate
              token={token}
            />
          )}

          {panel === 'quiz' && (
            <section>
              <Heading
                kicker="PRELIMS / ACTIVE RECALL"
                title="Pressure-test a topic."
              />

              <form
                className="quiz-start"
                onSubmit={generateQuiz}
              >
                <input
                  required
                  value={topic}
                  onChange={event =>
                    setTopic(
                      event.target.value
                    )
                  }
                  placeholder="Fundamental Rights, Parliament, federalism..."
                />

                <button
                  className="dark-button"
                  type="submit"
                >
                  Generate drill
                  <b>-</b>
                </button>
              </form>

              {quiz?.map(
                (item, index) => (
                  <article
                    className="surface question"
                    key={item.id}
                  >
                    <span className="kicker">
                      QUESTION{' '}
                      {String(index + 1).padStart(
                        2,
                        '0'
                      )}
                    </span>

                    <h3>
                      {item.question}
                    </h3>

                    {item.options.map(
                      (
                        option,
                        optionIndex
                      ) => (
                        <label
                          className="option"
                          key={option}
                        >
                          <input
                            type="radio"
                            name={`q-${item.id}`}
                            onChange={() =>
                              submitAnswer(
                                item.id,
                                optionIndex
                              )
                            }
                          />

                          <span>
                            {String.fromCharCode(
                              65 + optionIndex
                            )}
                            . {option}
                          </span>
                        </label>
                      )
                    )}

                    {results[item.id] && (
                      <p className="result">
                        {results[item.id]}
                      </p>
                    )}
                  </article>
                )
              )}
            </section>
          )}

          {panel === 'log' && (
            <section>
              <Heading
                kicker="KEEP THE RECEIPT"
                title="Log focused work."
              />

              <form
                className="surface session"
                onSubmit={logSession}
              >
                <label>
                  Topic
                  <input
                    required
                    value={session.topic}
                    onChange={event =>
                      setSession({
                        ...session,
                        topic:
                          event.target.value,
                      })
                    }
                    placeholder="Indian Polity"
                  />
                </label>

                <label>
                  Mode
                  <select
                    value={session.mode}
                    onChange={event =>
                      setSession({
                        ...session,
                        mode:
                          event.target.value,
                      })
                    }
                  >
                    <option>
                      study
                    </option>
                    <option>
                      revise
                    </option>
                    <option>
                      active recall
                    </option>
                    <option>
                      mains answer
                    </option>
                    <option>
                      prelims quiz
                    </option>
                  </select>
                </label>

                <label>
                  Minutes
                  <input
                    type="number"
                    min="1"
                    max="720"
                    value={session.minutes}
                    onChange={event =>
                      setSession({
                        ...session,
                        minutes:
                          event.target.value,
                      })
                    }
                  />
                </label>

                <label className="wide">
                  Notes
                  <textarea
                    value={session.notes}
                    onChange={event =>
                      setSession({
                        ...session,
                        notes:
                          event.target.value,
                      })
                    }
                    placeholder="What did you understand or leave unresolved?"
                  />
                </label>

                <button className="dark-button">
                  Save session
                  <b></b>
                </button>
              </form>
            </section>
          )}
        </section>
      </div>
    </div>
  )
}


export default function App() {
  const [token, setToken] = useState(
    localStorage.getItem('upsc_token')
  )

  const [email, setEmail] = useState(
    localStorage.getItem('upsc_email')
  )

  const login = (
    nextToken,
    nextEmail
  ) => {
    localStorage.setItem(
      'upsc_token',
      nextToken
    )

    localStorage.setItem(
      'upsc_email',
      nextEmail
    )

    setToken(nextToken)
    setEmail(nextEmail)
  }

  const logout = () => {
    localStorage.removeItem('upsc_token')
    localStorage.removeItem('upsc_email')
    setToken(null)
    setEmail(null)
  }

  return token ? (
    <StudyRoom
      token={token}
      email={email}
      onLogout={logout}
    />
  ) : (
    <Auth onLogin={login} />
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import './StudyRoom.css'

const API =
  import.meta.env.VITE_API_URL ||
  localStorage.getItem('upsc_api_url') ||
  'http://localhost:8000'

async function request(path, options = {}, token) {
  const isFormData =
    typeof FormData !== 'undefined' &&
    options.body instanceof FormData

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(isFormData
        ? {}
        : { 'Content-Type': 'application/json' }),
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
  const [inputMode, setInputMode] =
    useState('type')
  const [files, setFiles] = useState([])
  const [transcription, setTranscription] =
    useState(null)

  const MAX_FILES = 6

  function addFiles(event) {
    const picked = Array.from(
      event.target.files || []
    )

    setFiles(current => {
      const merged = [
        ...current,
        ...picked.filter(
          file => !current.some(
            existing =>
              existing.name === file.name &&
              existing.size === file.size
          )
        ),
      ]

      if (merged.length > MAX_FILES) {
        setMessage(
          `Attach at most ${MAX_FILES} files.`
        )
      }

      return merged.slice(0, MAX_FILES)
    })

    setMessage('')
    event.target.value = ''
  }

  function removeFile(index) {
    setFiles(current =>
      current.filter((_, i) => i !== index)
    )
  }

  function buildUploadBody(extra = {}) {
    const body = new FormData()

    body.append(
      'question',
      question.trim()
    )
    body.append('paper', paper)
    body.append(
      'word_limit',
      String(wordLimit)
    )

    Object.entries(extra).forEach(
      ([key, value]) =>
        body.append(key, value)
    )

    files.forEach(file =>
      body.append('files', file)
    )

    return body
  }

  async function transcribeFiles() {
    if (!files.length) {
      setMessage(
        'Attach a photo or PDF of your handwritten answer first.'
      )
      return
    }

    setLoading(true)
    setMessage('')

    try {
      const data = await request(
        '/mains/transcribe',
        {
          method: 'POST',
          body: buildUploadBody(),
        },
        token
      )

      setAnswer(data.answer || '')
      setTranscription(data.transcription)
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not read that upload.'
      )
    } finally {
      setLoading(false)
    }
  }

  async function evaluate(event) {
    event.preventDefault()

    if (!question.trim()) {
      setMessage('Enter the question.')
      return
    }

    if (inputMode === 'type' && !answer.trim()) {
      setMessage('Enter your answer.')
      return
    }

    if (
      inputMode === 'upload' &&
      !files.length
    ) {
      setMessage(
        'Attach a photo or PDF of your handwritten answer.'
      )
      return
    }

    setLoading(true)
    setResult(null)
    setMessage('')

    try {
      const uploading = inputMode === 'upload'

      const data = await request(
        uploading
          ? '/mains/evaluate-upload'
          : '/mains/evaluate',
        {
          method: 'POST',
          body: uploading
            ? buildUploadBody()
            : JSON.stringify({
                question,
                answer,
                paper,
                word_limit: wordLimit,
              }),
        },
        token
      )

      setResult(data)

      if (uploading) {
        setAnswer(data.answer || '')
        setTranscription(data.transcription)
      }
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

        <div className="answer-source-toggle">
          <button
            type="button"
            className={
              inputMode === 'type'
                ? 'source-chip active'
                : 'source-chip'
            }
            onClick={() =>
              setInputMode('type')
            }
          >
            Type my answer
          </button>

          <button
            type="button"
            className={
              inputMode === 'upload'
                ? 'source-chip active'
                : 'source-chip'
            }
            onClick={() =>
              setInputMode('upload')
            }
          >
            Upload handwritten
          </button>
        </div>

        {inputMode === 'upload' && (
          <div className="upload-panel">
            <label className="upload-dropzone">
              <input
                type="file"
                multiple
                accept="image/*,application/pdf,.pdf"
                onChange={addFiles}
              />
              <strong>
                Add photos or a PDF
              </strong>
              <span>
                Upload clear, well-lit photos of your
                handwritten answer, or a scanned PDF
                (up to {MAX_FILES} files).
              </span>
            </label>

            {files.length > 0 && (
              <ul className="upload-file-list">
                {files.map((file, index) => (
                  <li key={`${file.name}-${file.size}`}>
                    <span>
                      {file.name}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        removeFile(index)
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <button
              type="button"
              className="ghost-button"
              disabled={loading || !files.length}
              onClick={transcribeFiles}
            >
              {loading
                ? 'Reading...'
                : 'Read handwriting first'}
            </button>

            {transcription && (
              <small className="transcription-meta">
                Read {transcription.pages || 0}{' '}
                page(s) with{' '}
                {transcription.engine}. Proofread
                below before evaluating.
              </small>
            )}

            {Array.isArray(
              transcription?.warnings
            ) &&
              transcription.warnings.map(
                (warning, index) => (
                  <small
                    key={index}
                    className="transcription-warning"
                  >
                    {warning}
                  </small>
                )
              )}
          </div>
        )}

        <label className="wide">
          <span>
            {inputMode === 'upload'
              ? 'Transcribed Answer'
              : 'Your Answer'}
          </span>
          <textarea
            className="evaluation-answer-input"
            value={answer}
            onChange={event =>
              setAnswer(event.target.value)
            }
            placeholder={
              inputMode === 'upload'
                ? 'Your uploaded answer will appear here. You can correct any misread words before evaluating.'
                : 'Write your answer here. Try to answer first without seeing an AI draft.'
            }
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


function formatChatTime(value) {
  if (!value) return ''

  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return ''
  }

  return parsed.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}


function ChatRoom({ token }) {
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [starters, setStarters] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const threadRef = useRef(null)

  const isEmpty = messages.length === 0

  useEffect(() => {
    loadSessions()
    loadStarters()
  }, [token])

  useEffect(() => {
    const node = threadRef.current

    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, loading])

  async function loadSessions() {
    try {
      const data = await request(
        '/ask/chat/sessions',
        {},
        token
      )
      setSessions(Array.isArray(data) ? data : [])
    } catch (err) {
      setSessions([])
    }
  }

  async function loadStarters() {
    try {
      const data = await request(
        '/ask/chat/starter-topics',
        {},
        token
      )
      setStarters(data.topics || [])
    } catch (err) {
      setStarters([])
    }
  }

  async function openSession(id) {
    setError('')
    setActiveId(id)
    setInput('')

    try {
      const data = await request(
        `/ask/chat/sessions/${id}`,
        {},
        token
      )
      setMessages(data.messages || [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not open that chat.'
      )
    }
  }

  function startNewChat() {
    setActiveId(null)
    setMessages([])
    setInput('')
    setError('')
  }

  async function removeSession(id) {
    try {
      await request(
        `/ask/chat/sessions/${id}`,
        { method: 'DELETE' },
        token
      )
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not delete that chat.'
      )
      return
    }

    if (activeId === id) {
      startNewChat()
    }

    loadSessions()
  }

  async function send(text) {
    const question = (text || '').trim()

    if (!question || loading) return

    setLoading(true)
    setError('')
    setInput('')

    const pending = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: question,
      suggestions: [],
    }

    setMessages(current => [...current, pending])

    try {
      const data = await request(
        '/ask/chat',
        {
          method: 'POST',
          body: JSON.stringify({
            question,
            session_id: activeId,
          }),
        },
        token
      )

      const sessionId = data.session_id
      setActiveId(sessionId || null)

      if (typeof data.answer === 'string' && data.answer.trim()) {
        setMessages(current => [
          ...current.map(item =>
            item.id === pending.id
              ? {
                  ...item,
                  id: `user-${Date.now()}`,
                }
              : item
          ),
          {
            id: `answer-${Date.now()}`,
            role: 'assistant',
            content: data.answer,
            suggestions: Array.isArray(data.suggestions)
              ? data.suggestions
              : [],
          },
        ])
      }

      loadSessions()

      if (
        sessionId &&
        (typeof data.answer !== 'string' || !data.answer.trim())
      ) {
        try {
          const savedSession = await request(
            `/ask/chat/sessions/${sessionId}`,
            {},
            token
          )
          const savedMessages = Array.isArray(savedSession.messages)
            ? savedSession.messages
            : []
          let latestUserIndex = -1

          for (let index = savedMessages.length - 1; index >= 0; index -= 1) {
            const message = savedMessages[index]

            if (
              message.role === 'user' &&
              message.content === question
            ) {
              latestUserIndex = index
              break
            }
          }

          const savedAnswer = savedMessages
            .slice(latestUserIndex + 1)
            .find(message =>
              message.role === 'assistant' &&
              typeof message.content === 'string' &&
              message.content.trim()
            )

          if (latestUserIndex >= 0 && savedAnswer) {
            setMessages(savedMessages)
          } else {
            setError(
              'Your question was saved, but its answer is still unavailable. Please try reopening this chat shortly.'
            )
          }
        } catch (refreshError) {
          setError(
            refreshError instanceof Error
              ? `Your answer was saved, but the chat could not refresh: ${refreshError.message}`
              : 'Your answer was saved, but the chat could not refresh.'
          )
        }
      }

      if (!sessionId && (typeof data.answer !== 'string' || !data.answer.trim())) {
        setError(
          'Your question was sent, but the server did not return a chat session or answer.'
        )
      }
    } catch (err) {
      setMessages(current =>
        current.filter(item => item.id !== pending.id)
      )
      setInput(question)
      setError(
        err instanceof Error
          ? err.message
          : 'Could not complete that question.'
      )
    } finally {
      setLoading(false)
    }
  }

  function submit(event) {
    event.preventDefault()
    send(input)
  }

  return (
    <section>
      <Heading
        kicker="STUDY CHAT"
        title="Learn one thing at a time."
      />

      <p className="tool-intro">
        Ask anything about your syllabus. Each reply comes with
        suggested next topics so you always know what to
        study after this.
      </p>

      <div className="chat-layout">
        <aside className="chat-sidebar">
          <button
            className="chat-new-button"
            type="button"
            onClick={startNewChat}
          >
            + New chat
          </button>

          {sessions.length === 0 && (
            <p className="chat-sidebar-empty">
              Your saved chats will appear
              here.
            </p>
          )}

          {sessions.map(session => (
            <div
              key={session.id}
              className={
                session.id === activeId
                  ? 'chat-session active'
                  : 'chat-session'
              }
            >
              <button
                type="button"
                className="chat-session-open"
                onClick={() =>
                  openSession(session.id)
                }
              >
                <strong>{session.title}</strong>
                <small>
                  {session.message_count}{' '}
                  message(s) ·{' '}
                  {formatChatTime(session.updated_at)}
                </small>
              </button>

              <button
                type="button"
                className="chat-session-delete"
                onClick={() =>
                  removeSession(session.id)
                }
              >
                Delete
              </button>
            </div>
          ))}
        </aside>

        <div className="chat-main">
          <div
            className="chat-thread"
            ref={threadRef}
          >
            {isEmpty ? (
              <div className="chat-empty">
                <h3>
                  What would you like to
                  understand today?
                </h3>

                <p>
                  Pick a topic to begin, or ask
                  your own question below.
                </p>

                <div className="chat-starters">
                  {starters.map(topic => (
                    <button
                      key={topic}
                      type="button"
                      onClick={() => send(topic)}
                    >
                      {topic}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map(message => (
                <div key={message.id}>
                  <div
                    className={
                      message.role === 'user'
                        ? 'chat-bubble user'
                        : 'chat-bubble assistant'
                    }
                  >
                    <AnswerText
                      answer={message.content}
                    />
                  </div>

                  {message.role === 'assistant' &&
                    Array.isArray(
                      message.suggestions
                    ) &&
                    message.suggestions.length >
                      0 && (
                      <div className="chat-suggestions">
                        <span className="chat-suggestions-label">
                          NEXT, TRY:
                        </span>

                        {message.suggestions.map(
                          suggestion => (
                            <button
                              key={suggestion}
                              type="button"
                              disabled={loading}
                              onClick={() =>
                                send(suggestion)
                              }
                            >
                              {suggestion}
                            </button>
                          )
                        )}
                      </div>
                    )}
                </div>
              ))
            )}

            {loading && (
              <div className="chat-bubble assistant chat-typing">
                Thinking...
              </div>
            )}
          </div>

          {error && (
            <div
              className="notice"
              onClick={() => setError('')}
            >
              {error}
            </div>
          )}

          <form
            className="ask-box chat-composer"
            onSubmit={submit}
          >
            <textarea
              required
              rows={1}
              minLength="2"
              value={input}
              onChange={event =>
                setInput(event.target.value)
              }
              onKeyDown={event => {
                if (
                  event.key === 'Enter' &&
                  !event.shiftKey
                ) {
                  event.preventDefault()
                  send(input)
                }
              }}
              placeholder="Message your UPSC study partner"
              aria-label="Message your UPSC study partner"
            />

            <button
              className="dark-button"
              type="submit"
              disabled={loading}
              aria-label={loading ? 'Sending message' : 'Send message'}
            >
              <span>{loading ? 'Sending...' : 'Send'}</span>
              <b aria-hidden="true">↑</b>
            </button>
          </form>
          <p className="chat-composer-hint">
            Check important facts against official UPSC sources.
          </p>
        </div>
      </div>
    </section>
  )
}


function PrelimsDrill({ token, onProgress }) {
  const [catalog, setCatalog] = useState([])
  const [subject, setSubject] = useState('')
  const [topic, setTopic] = useState('')
  const [questionCount, setQuestionCount] = useState(10)
  const [quizView, setQuizView] = useState('hub')
  const [quiz, setQuiz] = useState([])
  const [quizResponses, setQuizResponses] = useState([])
  const [quizQuestionIndex, setQuizQuestionIndex] = useState(0)
  const [quizSelectedOption, setQuizSelectedOption] = useState('')
  const [submittingQuestionId, setSubmittingQuestionId] = useState(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState('')
  const [curiosityQuestion, setCuriosityQuestion] = useState(null)
  const [curiosityChoice, setCuriosityChoice] = useState('')
  const [curiosityResult, setCuriosityResult] = useState(null)
  const [curiosityNotice, setCuriosityNotice] = useState('')
  const [curiosityLoading, setCuriosityLoading] = useState(true)
  const [curiosityDifficulty, setCuriosityDifficulty] = useState(2)
  const [seenQuestionIds, setSeenQuestionIds] = useState([])
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [loadingQuiz, setLoadingQuiz] = useState(false)
  const [error, setError] = useState('')
  const curiosityTokenLoaded = useRef(null)

  const selectedSubject = catalog.find(item => item.name === subject)
  const topics = selectedSubject?.topics || []

  useEffect(() => {
    let cancelled = false

    async function loadCatalog() {
      setLoadingCatalog(true)
      try {
        const data = await request('/quiz/catalog', {}, token)
        if (!cancelled) {
          setCatalog(Array.isArray(data.subjects) ? data.subjects : [])
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Could not load the question bank.'
          )
        }
      } finally {
        if (!cancelled) setLoadingCatalog(false)
      }
    }

    loadCatalog()
    return () => {
      cancelled = true
    }
  }, [token])

  const loadNextCuriosityQuestion = useCallback(async (
    targetDifficulty,
    excludedIds,
    initialLoad = false
  ) => {
    if (!initialLoad) {
      setCuriosityLoading(true)
      setCuriosityNotice('')
      setCuriosityResult(null)
      setCuriosityChoice('')
    }

    try {
      const params = new URLSearchParams({
        target_difficulty: String(targetDifficulty),
      })
      excludedIds.forEach(id => params.append('exclude', String(id)))
      const question = await request(
        `/quiz/practice/next?${params.toString()}`,
        {},
        token
      )
      setCuriosityQuestion(question)
      setSeenQuestionIds(current =>
        current.includes(question.bank_id)
          ? current
          : [...current, question.bank_id]
      )
    } catch (err) {
      setCuriosityQuestion(null)
      setCuriosityNotice(
        err instanceof Error
          ? err.message
          : 'Could not load the next practice question.'
      )
    } finally {
      setCuriosityLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (curiosityTokenLoaded.current === token) return
    curiosityTokenLoaded.current = token
    loadNextCuriosityQuestion(2, [], true)
  }, [loadNextCuriosityQuestion, token])

  async function answerCuriosityQuestion(selectedOption = curiosityChoice) {
    if (!curiosityQuestion || !selectedOption || curiosityResult) return

    setCuriosityChoice(selectedOption)
    setCuriosityLoading(true)
    setCuriosityNotice('')

    try {
      const result = await request(
        '/quiz/submit',
        {
          method: 'POST',
          body: JSON.stringify({
            quiz_attempt_id: curiosityQuestion.id,
            selected_option: selectedOption,
          }),
        },
        token
      )
      setCuriosityResult(result)
      setCuriosityDifficulty(
        result.correct
          ? Math.min(curiosityQuestion.difficulty + 1, 3)
          : Math.max(curiosityQuestion.difficulty - 1, 1)
      )
      onProgress()
    } catch (err) {
      setCuriosityNotice(
        err instanceof Error
          ? err.message
          : 'Could not submit your answer.'
      )
    } finally {
      setCuriosityLoading(false)
    }
  }

  function nextCuriosityQuestion() {
    loadNextCuriosityQuestion(curiosityDifficulty, seenQuestionIds)
  }

  async function startFreshCuriosityRound() {
    setSeenQuestionIds([])
    await loadNextCuriosityQuestion(curiosityDifficulty, [])
  }

  async function startQuiz(event) {
    event.preventDefault()
    setLoadingQuiz(true)
    setError('')

    try {
      const data = await request(
        '/quiz/generate',
        {
          method: 'POST',
          body: JSON.stringify({
            subject: subject || null,
            topic: topic || null,
            num_questions: Number(questionCount),
          }),
        },
        token
      )
      const questions = Array.isArray(data.questions) ? data.questions : []
      if (questions.length === 0) {
        setError('No questions are available for this practice set yet.')
        return
      }

      setQuiz(questions)
      setQuizResponses([])
      setQuizQuestionIndex(0)
      setQuizSelectedOption('')
      setReviewError('')
      setQuizView('quiz')
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not assemble this practice set.'
      )
    } finally {
      setLoadingQuiz(false)
    }
  }

  async function recordQuizAnswer(questionId, selectedOption) {
    if (
      quizResponses.some(response => response.questionId === questionId) ||
      submittingQuestionId === questionId
    ) return
    setSubmittingQuestionId(questionId)
    setError('')

    try {
      const result = await request(
        '/quiz/submit',
        {
          method: 'POST',
          body: JSON.stringify({
            quiz_attempt_id: questionId,
            selected_option: selectedOption,
          }),
        },
        token
      )
      advanceQuiz({
        questionId,
        status: result.correct ? 'correct' : 'incorrect',
        selectedOption: result.selected_option,
        correctOption: result.correct_option,
      })
      onProgress()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not submit your answer.'
      )
    } finally {
      setSubmittingQuestionId(null)
    }
  }

  async function loadQuizAnswerReview(responses) {
    setReviewLoading(true)
    setReviewError('')

    try {
      const data = await request(
        '/quiz/review',
        {
          method: 'POST',
          body: JSON.stringify({
            attempt_ids: responses.map(response => response.questionId),
          }),
        },
        token
      )
      const answers = new Map(
        data.answers.map(answer => [answer.attempt_id, answer.correct_option])
      )
      setQuizResponses(current =>
        current.map(response => ({
          ...response,
          correctOption: response.correctOption || answers.get(response.questionId),
        }))
      )
    } catch (err) {
      setReviewError(
        err instanceof Error
          ? err.message
          : 'Could not load the answer key for this quiz.'
      )
    } finally {
      setReviewLoading(false)
    }
  }

  function advanceQuiz(response) {
    const nextResponses = [...quizResponses, response]
    setQuizResponses(nextResponses)
    setQuizSelectedOption('')

    if (quizQuestionIndex + 1 === quiz.length) {
      setQuizView('results')
      loadQuizAnswerReview(nextResponses)
    } else {
      setQuizQuestionIndex(index => index + 1)
    }
  }

  function skipCurrentQuestion() {
    if (submittingQuestionId !== null) return
    const question = quiz[quizQuestionIndex]
    if (!question) return

    advanceQuiz({
      questionId: question.id,
      status: 'skipped',
      selectedOption: null,
      correctOption: null,
    })
  }

  function returnToPracticeHub() {
    setQuizView('hub')
    setQuiz([])
    setQuizResponses([])
    setQuizQuestionIndex(0)
    setQuizSelectedOption('')
    setReviewError('')
  }

  /*
   * The compact adaptive loop below always samples across all subjects.
   * The subject/topic controls only affect the separate longer practice set.
   */
  const curiosityFeedback = curiosityResult
    ? curiosityResult.correct
      ? curiosityQuestion.difficulty < 3
        ? 'Correct! Let’s try a slightly harder one.'
        : 'Correct! You’re at challenge level—keep the streak going.'
      : curiosityQuestion.difficulty > 1
        ? `Not quite. The answer is ${curiosityResult.correct_option}. Let’s build confidence with an easier one.`
        : `Not quite. The answer is ${curiosityResult.correct_option}. We’ll stay with a gentle question and keep learning.`
    : ''

  if (quizView === 'quiz') {
    const question = quiz[quizQuestionIndex]

    return (
      <section className="prelims-page prelims-quiz-page">
        <button
          className="outline-button prelims-back-button"
          type="button"
          onClick={returnToPracticeHub}
          disabled={submittingQuestionId !== null}
        >
          ← Back to practice setup
        </button>
        <div className="prelims-quiz-heading">
          <div>
            <span className="kicker">UPSC PRELIMS / PRACTICE QUIZ</span>
            <h1>Stay with one question at a time.</h1>
          </div>
          <span className="prelims-quiz-count">
            Question {quizQuestionIndex + 1} of {quiz.length}
          </span>
        </div>
        <progress
          className="prelims-quiz-progress"
          value={quizQuestionIndex + 1}
          max={quiz.length}
          aria-label={`Question ${quizQuestionIndex + 1} of ${quiz.length}`}
        />
        {error && <div className="notice" role="alert">{error}</div>}
        {question && (
          <article className="surface prelims-question prelims-current-question">
            <div className="prelims-question-meta">
              <span>{question.year} · {question.subject} · {question.topic}</span>
              <span>{question.source}</span>
            </div>
            <h2>{question.question}</h2>
            <div className="prelims-options">
              {question.options.map((option, index) => {
                const letter = String.fromCharCode(65 + index)
                return (
                  <label
                    className={[
                      'prelims-option',
                      quizSelectedOption === letter ? 'selected' : '',
                    ].filter(Boolean).join(' ')}
                    key={`${question.id}-${letter}`}
                  >
                    <input
                      type="radio"
                      name={`quiz-question-${question.id}`}
                      value={letter}
                      checked={quizSelectedOption === letter}
                      disabled={submittingQuestionId === question.id}
                      onChange={() => setQuizSelectedOption(letter)}
                    />
                    <span className="prelims-option-letter">{letter}</span>
                    <span>{option}</span>
                  </label>
                )
              })}
            </div>
            <div className="prelims-quiz-actions">
              <button
                className="outline-button"
                type="button"
                onClick={skipCurrentQuestion}
                disabled={submittingQuestionId !== null}
              >
                Skip question
              </button>
              <button
                className="dark-button"
                type="button"
                onClick={() => recordQuizAnswer(question.id, quizSelectedOption)}
                disabled={!quizSelectedOption || submittingQuestionId !== null}
              >
                {submittingQuestionId === question.id
                  ? 'Submitting…'
                  : quizQuestionIndex + 1 === quiz.length
                    ? 'Submit & see results'
                    : 'Submit & next'}
                <b aria-hidden="true">→</b>
              </button>
            </div>
          </article>
        )}
      </section>
    )
  }

  if (quizView === 'results') {
    const correctAnswers = quizResponses.filter(item => item.status === 'correct').length
    const incorrectAnswers = quizResponses.filter(item => item.status === 'incorrect').length
    const skippedAnswers = quizResponses.filter(item => item.status === 'skipped').length
    const attemptedAnswers = correctAnswers + incorrectAnswers

    return (
      <section className="prelims-page prelims-results-page">
        <span className="kicker">UPSC PRELIMS / QUIZ COMPLETE</span>
        <h1>Your practice results</h1>
        <p className="tool-intro">
          You answered {attemptedAnswers} of {quiz.length} questions and skipped {skippedAnswers}.
        </p>
        <div className="prelims-result-summary">
          <article>
            <strong>{correctAnswers}</strong>
            <span>Correct</span>
          </article>
          <article>
            <strong>{incorrectAnswers}</strong>
            <span>Incorrect</span>
          </article>
          <article>
            <strong>{skippedAnswers}</strong>
            <span>Skipped</span>
          </article>
          <article>
            <strong>{attemptedAnswers ? Math.round(correctAnswers / attemptedAnswers * 100) : 0}%</strong>
            <span>Accuracy</span>
          </article>
        </div>
        <div className="prelims-result-review">
          {reviewError && (
            <div className="notice" role="alert">
              {reviewError}
              <button
                className="outline-button"
                type="button"
                onClick={() => loadQuizAnswerReview(quizResponses)}
                disabled={reviewLoading}
              >
                {reviewLoading ? 'Loading answers…' : 'Retry answer review'}
              </button>
            </div>
          )}
          {quizResponses.map((response, index) => {
            const question = quiz.find(item => item.id === response.questionId)
            if (!question) return null

            return (
              <article className="surface prelims-result-item" key={response.questionId}>
                <div className="prelims-question-meta">
                  <span>QUESTION {String(index + 1).padStart(2, '0')}</span>
                  <span className={`prelims-result-status ${response.status}`}>
                    {response.status}
                  </span>
                </div>
                <h2>{question.question}</h2>
                <p>
                  {response.status === 'skipped'
                    ? `Skipped · Correct answer: ${response.correctOption || (reviewLoading ? 'Loading…' : 'Unavailable')}`
                    : `Your answer: ${response.selectedOption} · Correct answer: ${response.correctOption}`}
                </p>
                {question.explanation && <p>{question.explanation}</p>}
              </article>
            )
          })}
        </div>
        <button className="dark-button" type="button" onClick={returnToPracticeHub}>
          Back to practice setup <b aria-hidden="true">→</b>
        </button>
      </section>
    )
  }

  return (
    <section className="prelims-page">
      <Heading
        kicker="UPSC PRELIMS / QUESTION BANK"
        title="Practice real questions."
      />

      <p className="tool-intro">
        Build a practice set from sourced previous-year questions. AI only
        selects and orders questions already in the bank; it never writes
        questions.
      </p>

      <form className="prelims-controls" onSubmit={startQuiz}>
        <label>
          Subject
          <select
            value={subject}
            onChange={event => {
              setSubject(event.target.value)
              setTopic('')
            }}
            disabled={loadingCatalog || catalog.length === 0}
          >
            <option value="">All subjects</option>
            {catalog.map(item => (
              <option key={item.name} value={item.name}>
                {item.name} ({item.question_count})
              </option>
            ))}
          </select>
        </label>

        <label>
          Topic
          <select
            value={topic}
            onChange={event => setTopic(event.target.value)}
            disabled={loadingCatalog || topics.length === 0}
          >
            <option value="">All topics</option>
            {topics.map(item => (
              <option key={item.name} value={item.name}>
                {item.name} ({item.question_count})
              </option>
            ))}
          </select>
        </label>

        <label>
          Questions
          <select
            value={questionCount}
            onChange={event => setQuestionCount(Number(event.target.value))}
          >
            {[5, 10, 15, 20].map(count => (
              <option key={count} value={count}>{count}</option>
            ))}
          </select>
        </label>

        <button
          className="dark-button"
          type="submit"
          disabled={loadingQuiz || loadingCatalog || catalog.length === 0}
        >
          {loadingQuiz ? 'Assembling...' : 'Start practice'}
          <b aria-hidden="true">→</b>
        </button>
      </form>

      <article className="curiosity-card">
        {curiosityLoading && (
          <p className="curiosity-loading" role="status">
            Finding your next question…
          </p>
        )}

        {!curiosityLoading && curiosityQuestion && (
          <>
            <h3 className="curiosity-question">
              {curiosityQuestion.question}
            </h3>
            <div className="curiosity-options">
              {curiosityQuestion.options.map((option, index) => {
                const letter = String.fromCharCode(65 + index)
                const isCorrect = curiosityResult?.correct_option === letter
                const isWrongPick =
                  curiosityResult?.selected_option === letter &&
                  !curiosityResult.correct
                return (
                  <label
                    className={[
                      'curiosity-option',
                      isCorrect ? 'correct' : '',
                      isWrongPick ? 'incorrect' : '',
                    ].filter(Boolean).join(' ')}
                    key={`${curiosityQuestion.id}-${letter}`}
                  >
                    <input
                      type="radio"
                      name={`curiosity-${curiosityQuestion.id}`}
                      value={letter}
                      checked={curiosityChoice === letter}
                      disabled={Boolean(curiosityResult) || curiosityLoading}
                      onChange={() => answerCuriosityQuestion(letter)}
                    />
                    <span className="curiosity-option-letter">{letter}</span>
                    <span>{option}</span>
                  </label>
                )
              })}
            </div>

            {curiosityResult && (
              <div className="curiosity-after-answer">
                <p
                  className={`curiosity-feedback ${curiosityResult.correct ? 'correct' : 'incorrect'}`}
                  role="status"
                >
                  {curiosityFeedback}
                </p>
                <button
                  className="dark-button"
                  type="button"
                  onClick={nextCuriosityQuestion}
                  disabled={curiosityLoading}
                >
                  Next question <b aria-hidden="true">→</b>
                </button>
              </div>
            )}
          </>
        )}

        {!curiosityLoading && !curiosityQuestion && (
          <div className="curiosity-empty">
            <p>{curiosityNotice || 'No answer-keyed questions are available yet.'}</p>
            {curiosityNotice.toLowerCase().includes('explored all available questions') && (
              <button
                className="outline-button"
                type="button"
                onClick={startFreshCuriosityRound}
              >
                Start a fresh round
              </button>
            )}
          </div>
        )}

        {curiosityNotice && curiosityQuestion && (
          <div className="notice" role="alert">{curiosityNotice}</div>
        )}
      </article>

      {loadingCatalog && <p className="muted">Loading available questions…</p>}

      {!loadingCatalog && catalog.length === 0 && (
        <div className="prelims-empty">
          <h3>Your question bank is ready for PYQs.</h3>
          <p>
            No answer-keyed questions have been imported yet. Import an
            official searchable GS Paper I PDF with its answer-key CSV using
            <code>scripts/import_prelims.py</code>.
          </p>
        </div>
      )}

      {error && <div className="notice" role="alert">{error}</div>}
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
    ['overview', '⌂', 'Overview'],
    ['ask', '✦', 'Study chat'],
    ['mains', '▤', 'Mains Drafting'],
    [
      'evaluate',
      '✓',
      'Answer Evaluation',
    ],
    ['quiz', '◉', 'Prelims Drill'],
    ['log', '+', 'Log a session'],
  ]

  return (
    <div className={`room ${panel === 'ask' ? 'chat-mode' : ''}`}>
      <header className="header">
        <div>
          <span className="room-brand-mark" aria-hidden="true">U</span>
          <span className="kicker">UPSC STUDY PARTNER</span>
          <h2>Study Room</h2>
        </div>

        <div className="header-right">
          <span>{email}</span>
          <button onClick={onLogout} aria-label="Sign out">
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
                aria-label={label}
                aria-current={panel === key ? 'page' : undefined}
                title={label}
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
            <ChatRoom token={token} />
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
            <PrelimsDrill token={token} onProgress={refresh} />
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

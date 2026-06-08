using UnityEngine;
using UnityEngine.AI;

[RequireComponent(typeof(NavMeshAgent))]
public class EnemyAI : MonoBehaviour
{
    public enum Difficulty { Easy, Normal, Hard }
    public enum State { Patrol, Chase, Attack, Hurt, Search, Cover }

    [Header("Combat")]
    public float moveSpeed = -1f;
    public float attackDamage = 8f;
    public float attackRange = 14f;
    public float attackInterval = -1f;
    public float viewDistance = 28f;
    public float viewAngle = 120f;
    public float spawnAwarenessDelay = 3f;

    [Header("Behavior")]
    public float fireInterval = 1.2f;
    public float reactionDelay = 0.5f;
    public float hitChance = 0.7f;
    public float searchTime = 5f;
    public float hurtTime = 0.5f;
    public float coverTime = 2.5f;
    public float coverChance = 0.6f;

    [Header("Points")]
    public Transform[] patrolPoints;
    public Transform[] coverPoints;

    public Difficulty difficulty = Difficulty.Normal;

    private NavMeshAgent agent;
    private Transform player;
    private PlayerHealth playerHealth;
    private EnemyHealth myHealth;

    private State state = State.Patrol;
    private float baseSpeed;
    private float fireTimer;
    private float stateTimer;
    private float reactTimer;
    private float lostTimer;
    private Vector3 lastKnownPos;
    private float lastHealth;
    private float activeAt;

    void Start()
    {
        agent = GetComponent<NavMeshAgent>();
        if (moveSpeed > 0f)
            agent.speed = moveSpeed;
        if (attackInterval > 0f)
            fireInterval = attackInterval;

        baseSpeed = agent.speed;

        playerHealth = Object.FindFirstObjectByType<PlayerHealth>();
        if (playerHealth != null)
            player = playerHealth.transform;

        myHealth = GetComponent<EnemyHealth>();
        if (myHealth != null)
            lastHealth = myHealth.health;

        activeAt = Time.time + spawnAwarenessDelay;
        ApplyDifficulty();
        GoToNextPatrol();
    }

    void Update()
    {
        if (player == null || agent == null)
            return;

        if (GameOver())
        {
            if (agent.isOnNavMesh)
                agent.ResetPath();
            return;
        }

        if (myHealth != null && myHealth.health < lastHealth)
        {
            lastHealth = myHealth.health;
            OnDamaged();
        }

        switch (state)
        {
            case State.Patrol: Patrol(); break;
            case State.Chase: Chase(); break;
            case State.Attack: Attack(); break;
            case State.Hurt: HurtState(); break;
            case State.Search: SearchState(); break;
            case State.Cover: CoverState(); break;
        }
    }

    private void ApplyDifficulty()
    {
        switch (difficulty)
        {
            case Difficulty.Easy:
                reactionDelay = 1.35f;
                hitChance = 0.18f;
                fireInterval = 2.8f;
                viewDistance = 20f;
                break;
            case Difficulty.Normal:
                reactionDelay = 1.15f;
                hitChance = 0.3f;
                fireInterval = 2.25f;
                viewDistance = 22f;
                break;
            case Difficulty.Hard:
                reactionDelay = 0.75f;
                hitChance = 0.52f;
                fireInterval = 1.55f;
                viewDistance = 28f;
                break;
        }
    }

    private void Patrol()
    {
        SetRun(false);
        if (CanSeePlayer())
        {
            EnterChase();
            return;
        }

        if (patrolPoints != null && patrolPoints.Length > 0 && agent.isOnNavMesh)
        {
            if (!agent.pathPending && agent.remainingDistance < 1.2f)
                GoToNextPatrol();
        }
    }

    private void Chase()
    {
        SetRun(true);
        bool canSee = CanSeePlayer();
        if (canSee)
        {
            lastKnownPos = player.position;
            lostTimer = 0f;
        }
        else
        {
            lostTimer += Time.deltaTime;
        }

        if (agent.isOnNavMesh)
            agent.SetDestination(canSee ? player.position : lastKnownPos);

        if (canSee && Distance() <= attackRange)
        {
            EnterAttack();
            return;
        }

        if (!canSee && lostTimer > 1.5f)
            EnterSearch();
    }

    private void Attack()
    {
        bool canSee = CanSeePlayer();
        FacePlayer();

        if (agent.isOnNavMesh)
            agent.SetDestination(transform.position);

        if (!canSee)
        {
            EnterChase();
            return;
        }

        lastKnownPos = player.position;
        if (Distance() > attackRange * 1.15f)
        {
            EnterChase();
            return;
        }

        reactTimer += Time.deltaTime;
        if (reactTimer < reactionDelay)
            return;

        fireTimer -= Time.deltaTime;
        if (fireTimer <= 0f)
        {
            fireTimer = fireInterval;
            Fire();
        }
    }

    private void HurtState()
    {
        if (agent.isOnNavMesh)
            agent.ResetPath();

        stateTimer -= Time.deltaTime;
        if (stateTimer <= 0f)
        {
            if (coverPoints != null && coverPoints.Length > 0 && Random.value < coverChance)
                EnterCover();
            else
                EnterChase();
        }
    }

    private void SearchState()
    {
        SetRun(true);
        if (CanSeePlayer())
        {
            EnterChase();
            return;
        }

        if (agent.isOnNavMesh)
            agent.SetDestination(lastKnownPos);

        stateTimer -= Time.deltaTime;
        if (stateTimer <= 0f)
        {
            state = State.Patrol;
            GoToNextPatrol();
        }
    }

    private void CoverState()
    {
        SetRun(true);
        if (CanSeePlayer())
            lastKnownPos = player.position;

        stateTimer -= Time.deltaTime;
        bool arrived = agent.isOnNavMesh && !agent.pathPending && agent.remainingDistance < 1f;
        if (stateTimer <= 0f || arrived)
            EnterChase();
    }

    private void OnDamaged()
    {
        if (player != null)
            lastKnownPos = player.position;

        state = State.Hurt;
        stateTimer = hurtTime;
        if (agent.isOnNavMesh)
            agent.ResetPath();
    }

    private void EnterChase()
    {
        state = State.Chase;
        lostTimer = 0f;
    }

    private void EnterAttack()
    {
        state = State.Attack;
        reactTimer = 0f;
        fireTimer = 0f;
    }

    private void EnterSearch()
    {
        state = State.Search;
        stateTimer = searchTime;
    }

    private void EnterCover()
    {
        state = State.Cover;
        stateTimer = coverTime;
        Transform cover = NearestCover();
        if (cover != null && agent.isOnNavMesh)
            agent.SetDestination(cover.position);
    }

    private bool CanSeePlayer()
    {
        if (player == null)
            return false;
        if (Time.time < activeAt)
            return false;

        Vector3 toPlayer = player.position - transform.position;
        float distance = toPlayer.magnitude;
        if (distance > viewDistance)
            return false;

        if (Vector3.Angle(transform.forward, toPlayer) > viewAngle * 0.5f)
            return false;

        return HasLineOfSight();
    }

    private bool HasLineOfSight()
    {
        Vector3 eye = transform.position + Vector3.up * 1.5f;
        Vector3 target = player.position + Vector3.up * 1f;
        Vector3 direction = target - eye;

        if (Physics.Raycast(eye, direction.normalized, out RaycastHit hit, direction.magnitude))
        {
            return hit.transform.GetComponent<PlayerHealth>() != null
                || hit.transform.GetComponentInParent<PlayerHealth>() != null;
        }

        return true;
    }

    private void Fire()
    {
        SpawnEnemyMuzzleFx();
        if (Random.value <= hitChance && playerHealth != null)
            playerHealth.TakeDamage(attackDamage);
    }

    private void SpawnEnemyMuzzleFx()
    {
        GameObject flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Destroy(flash.GetComponent<Collider>());
        flash.transform.position = transform.position + transform.forward * 0.7f + Vector3.up * 1.35f;
        flash.transform.localScale = Vector3.one * 0.18f;

        Renderer renderer = flash.GetComponent<Renderer>();
        if (renderer != null)
            renderer.material.color = new Color(1f, 0.72f, 0.12f);

        Destroy(flash, 0.08f);
    }

    private void FacePlayer()
    {
        Vector3 toPlayer = player.position - transform.position;
        toPlayer.y = 0f;
        if (toPlayer.sqrMagnitude > 0.01f)
        {
            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                Quaternion.LookRotation(toPlayer),
                12f * Time.deltaTime);
        }
    }

    private float Distance()
    {
        return Vector3.Distance(transform.position, player.position);
    }

    private void SetRun(bool run)
    {
        if (agent != null)
            agent.speed = run ? baseSpeed : baseSpeed * 0.5f;
    }

    private void GoToNextPatrol()
    {
        if (patrolPoints == null || patrolPoints.Length == 0 || !agent.isOnNavMesh)
            return;

        int index = Random.Range(0, patrolPoints.Length);
        if (patrolPoints[index] != null)
            agent.SetDestination(patrolPoints[index].position);
    }

    private Transform NearestCover()
    {
        Transform best = null;
        float bestDistance = Mathf.Infinity;
        if (coverPoints == null)
            return null;

        foreach (Transform cover in coverPoints)
        {
            if (cover == null)
                continue;

            float distance = Vector3.Distance(transform.position, cover.position);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = cover;
            }
        }

        return best;
    }

    private bool GameOver()
    {
        return GameManager.Instance != null &&
               GameManager.Instance.CurrentState != GameManager.State.Playing;
    }
}

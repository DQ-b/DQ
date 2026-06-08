using UnityEngine;

public class GunRaycast : MonoBehaviour
{
    public Camera fpsCam;
    public float damage = 25f;
    public float range = 100f;
    public int maxAmmo = 30;

    private int currentAmmo;

    public int CurrentAmmo { get { return currentAmmo; } }
    public int MaxAmmo { get { return maxAmmo; } }

    private void Start()
    {
        currentAmmo = maxAmmo;
        if (fpsCam == null)
            fpsCam = GetComponent<Camera>();
    }

    private void Update()
    {
        if (GameManager.Instance != null &&
            GameManager.Instance.CurrentState != GameManager.State.Playing)
            return;

        if (Input.GetMouseButtonDown(0) && currentAmmo > 0)
            Shoot();

        if (Input.GetKeyDown(KeyCode.R))
            currentAmmo = maxAmmo;
    }

    private void Shoot()
    {
        currentAmmo--;

        if (Physics.Raycast(fpsCam.transform.position, fpsCam.transform.forward, out RaycastHit hit, range))
        {
            EnemyHealth enemy = hit.transform.GetComponent<EnemyHealth>();
            if (enemy != null)
                enemy.TakeDamage(damage);

            Target target = hit.transform.GetComponent<Target>();
            if (target != null)
                target.TakeDamage(damage);
        }
    }
}
